"""L2 — Firewall semántico bilingüe (ES/EN) basado en reglas auditables.

Dos conjuntos de reglas intercambiables (para la búsqueda de variantes):

- ``legacy_cyber``: copia exacta de las reglas de NRE v2 (solo ciberseguridad e
  inyección). Se conserva para comparar.
- ``bilingual`` (por defecto): categorías de daño amplias en español e inglés con
  patrones conscientes de la intención: un término peligroso por sí solo NO bloquea
  ("¿por qué se prohibieron las armas químicas?"); se bloquea cuando aparece junto a
  una señal operativa (cómo hacer, pasos, conseguir, escribe..., sin que me atrapen).

Las reglas se escribieron mirando SOLO el split de desarrollo (ver eval/splits.py).
No es un clasificador aprendido: tiene falsos negativos y falsos positivos.
Inspecciona AMBOS canales: la petición del usuario y los datos externos (no confiables).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .text import fold

MAX_INPUT = 20000

# ---------------------------------------------------------------------------
# Reglas antiguas (NRE v2) — solo para la variante de comparación.
LEGACY_RULES: dict[str, list[str]] = {
    "PROMPT_INJECTION": [
        r"\bignora(r)? (todas |todo |las |tus )*(instrucciones|reglas|indicaciones)",
        r"\bignore (all |any |the |your )*(previous |prior |above )?(instructions|rules)",
        r"\b(olvida|olvidate de) (tus|las|todas las) (reglas|instrucciones)",
        r"\b(revela|muestra|imprime|reveal|print|show)( me)? (tu |el |your |the )?(prompt|system prompt|instrucciones del sistema|prompt del sistema)",
        r"\b(modo desarrollador|developer mode|modo dios|god mode)\b",
        r"\bjailbreak\b",
        r"\b(sin|without|no) (restricciones|filtros|reglas|restrictions|filters|rules)\b",
        r"\b(actua|finge|pretend|act) (como si|as if|that) (no )?(tuvieras|you have|you had)? ?(no )?(reglas|limites|rules|limits)",
        r"\bdan\b",
    ],
    "DESTRUCTIVE_ACTION": [
        r"rm\s+-rf",
        r"\bdrop\s+(table|database)\b",
        r"\b(borra|borrar|elimina|eliminar|delete|wipe)\b.{0,30}\b(todo|todos|todas|toda la|la base de datos|el disco|all|everything|database|disk)\b",
        r"\b(formatea|formatear|format)\b.{0,20}\b(disco|servidor|disk|drive|server)\b",
        r"\b(destruye|destroy)\b",
    ],
    "MALICIOUS_INTENT": [
        r"\bhack(ea|ear|ing)?\b",
        r"\bbypass\b",
        r"\b(evade|evadir|evadas)\b.{0,30}\b(seguridad|controles|deteccion|security|detection)\b",
        r"\b(exploit|malware|ransomware|keylogger|botnet|phishing)\b",
        r"\b(roba|robar|steal)\b.{0,30}\b(contrasenas|passwords|credenciales|credentials|datos|data)\b",
    ],
    "SECRET_EXFILTRATION": [
        r"\b(envia|manda|filtra|exfiltra|send|leak|exfiltrate)\b.{0,40}\b(contrasena|password|credencial|credential|api[ _-]?key|token|secreto|secret)",
    ],
}

# ---------------------------------------------------------------------------
# Señales de intención operativa (ES/EN).
CUE = (
    r"((^|[¿?.!:] *)como\b|\bcomo [a-z]+(ar|er|ir|arlo|arla|erlo|erla|irlo|irla|arle|erle)\b|\bcomo (puedo|podria|podemos|hago|hacer|se hace|se puede|se fabrica|fabrico|consigo|preparo|construyo|lograr|le hago|lo hago)\b"
    r"|\b(pasos|paso a paso|instrucciones|guia|tutorial|receta|manual|metodo|formula)\b"
    r"|\b(ensename|ensenar|explicame como|dime como|dime donde|ayudame a|quiero|necesito|voy a|planeo|pienso)\b"
    r"|\bdonde (puedo|consigo|compro|conseguir|comprar|venden)\b"
    r"|\b(escrib\w*|redact\w*|crea|crear|cree|genera|generar|disen\w*|desarroll\w*|elabor\w*|programa|programar|haz|hacer|dame|dar|proporcion\w*|publica|publicar|difund\w*|instruir|instruye|explique|explica|establezca|esbozo|esboza|construir|liberar|usar|utilizar|vender|venda)\b"
    r"|\b(forma|manera) (mas )?(facil|rapida|efectiva|segura|barata|sencilla)? ?de\b"
    r"|\bhow (to|do|does|can|could|would|should|might)\b"
    r"|\b(step[- ]by[- ]step|steps|instructions|guide|tutorial|recipe|walkthrough|blueprint)\b"
    r"|\b(teach|show|tell|help|explain to) (me|us|someone|people|users|children|kids)\b"
    r"|\b(i want|i need|i'm going|im going|i plan|let's|lets)\b"
    r"|\bwhere (can|do|could|to) (i |we )?(buy|get|find|obtain|purchase)\b"
    r"|\b(write|create|generate|draft|develop|design|compose|produce|provide|give|outline|build|make|publish|post|program|code|craft|devise|suggest|offer)\b"
    r"|\b(best|easiest|fastest|cheapest|most effective|quickest) way\b"
    r"|\b(fabric|sintetiz|produc|prepar|cultiv|consegu|obten|compr|construi|synthes|manufactur|obtain|acquir|weaponi|dispers|detona|detonat)\w*"
    r"|\bsin que (me|nos|lo|la|le|se|nadie)\b|\bwithout (getting caught|being (caught|detected|noticed|traced)|anyone (knowing|noticing|finding out))\b"
    r"|\b(que parezca|look like) (un |an )?(accidente|accident|suicidio|suicide)\b)"
)

PERSON = (
    r"(\ba (un|una|el|la|los|las|mi|mis|tu|su|sus|esa|ese|este|esta|esos|esas) [a-z]+|\bal [a-z]+|alguien|una persona|personas|gente|la gente|mi (esposa|esposo|pareja|novia|novio|ex|jefe|jefa|vecino|vecina|hermano|hermana|madre|padre|mama|papa|hijo|hija|suegra|suegro|maestro|maestra|companero|companera|amigo|amiga)|su |un hombre|una mujer|un policia|un juez|el presidente|"
    r"otros|otras|others|other users|otros usuarios|someone|somebody|a person|people|my (wife|husband|partner|girlfriend|boyfriend|ex|boss|neighbor|neighbour|brother|sister|mother|father|mom|dad|son|daughter|teacher|coworker|classmate|friend|roommate)|him|her|them|a man|a woman|a cop|police officer|the president|a politician|"
    r"[a-z]+ (sin que|without))"
)
MINOR = r"(nino|nina|ninos|ninas|menor|menores|bebe|bebes|adolescente|nene|child|children|kid|kids|minor|minors|baby|babies|toddler|infant|underage|preteen|teenager|\b1[0-7] ?(anos|year[s]?[- ]old|yo)\b|\b[1-9] ?(anos|year[s]?[- ]old|yo)\b)"

HARM_RULES: dict[str, list[tuple[str, bool]]] = {
    # (patrón, requiere_señal_operativa)
    "PROMPT_INJECTION": [
        (r"\bignora(r)? (todas |todo |las |tus |mis |sus )*(instrucciones|reglas|indicaciones|politicas)( anteriores| previas)?", False),
        (r"\bignore (all |any |the |your |previous |prior |above )+(instructions|rules|guidelines|policies)", False),
        (r"\b(olvida|olvidate de) (tus|las|todas las|todas tus) (reglas|instrucciones)", False),
        (r"\bdisregard (all |the |your |any )*(previous |prior )?(instructions|rules|guidelines)", False),
        (r"\b(revela|muestra|imprime|reveal|print|show|leak)( me)? (tu |el |your |the )?(system prompt|prompt del sistema|instrucciones del sistema|hidden prompt|initial prompt)", False),
        (r"\b(modo desarrollador|developer mode|modo dios|god mode|do anything now)\b", False),
        (r"\bjailbreak", False),
        (r"\b(desactiva|deshabilita|disable|turn off|override) (las |tus |the |your |all )*(restricciones|filtros|reglas|salvaguardas|safety|safeguards|restrictions|filters|guardrails|system policy|politica del sistema)", False),
        (r"\b(actua|finge|pretend|act) (como si|as if) (no )?(tuvieras|you have|you had) (no )?(reglas|limites|rules|limits|restrictions)", False),
    ],
    "DESTRUCTIVE_SYSTEM_ACTION": [
        (r"rm\s+-rf\s+/|rm\s+-rf\s+\*|\bmkfs\b|:\(\)\s*\{|del\s+/[fsq]", False),
        (r"\bdrop\s+(table|database)\b", False),
        (r"\b(borra|borrar|elimina|eliminar|delete|wipe|destruye|destroy)\b.{0,25}\b(base de datos de produccion|production database|todos los servidores|all servers|disco duro de|hard drive of|todos los respaldos|all backups)\b", False),
        (r"\b(formatea|formatear|format|wipe)\b.{0,20}\b(servidor|disco del servidor|server|hard drive|disco duro)\b", False),
    ],
    "WEAPONS_EXPLOSIVES": [
        (r"\b(bomba|bombas|explosivo|explosivos|artefacto explosivo|detonador|granada|molotov|dinamita|c-?4|tnt|nitroglicerina|polvora negra|"
         r"bomb|bombs|explosive|explosives|ied|detonator|grenade|dynamite|nitroglycerin|pipe bomb|pressure cooker bomb|napalm|thermite|termita)\b", True),
        (r"\b(arma|armas|pistola|rifle|escopeta|fusil|ametralladora|silenciador|municion|"
         r"gun|guns|firearm|firearms|weapon|weapons|pistol|rifle|shotgun|machine gun|silencer|suppressor|ammunition|ammo)\b"
         r".{0,60}\b(casera|caseras|fantasma|sin registro|sin numero|impresora 3d|automatic[ao]|ilegal|robad[ao]|untraceable|ghost|3d[- ]print|homemade|fully automatic|full auto|unregistered|illegal|stolen|without (a )?(license|background check|serial))", False),
        (r"\b(fabricar|construir|armar|hacer|conseguir|comprar|vender|traficar|convertir|make|build|assemble|manufacture|obtain|acquire|buy|sell|smuggle|traffic|convert|modify)\b.{0,40}\b(arma|armas|pistola|rifle|fusil|silenciador|gun|guns|firearm|firearms|weapon|weapons|pistol|silencer|suppressor)\b", True),
    ],
    "CBRN_WEAPONS": [
        (r"\b(sarin|tabun|soman|novichok|ricina|ricin|antrax|anthrax|botulin[ao]?|toxina botulinica|botulinum|gas nervioso|agente nervioso|nerve agent|nerve gas|gas mostaza|mustard gas|fosgeno|phosgene|cianuro|cyanide|"
         r"armas? quimicas?|armas? biologicas?|chemical weapons?|biological weapons?|bioweapons?|bomba sucia|dirty bomb|uranio enriquecido|enriched uranium|plutonio|plutonium|agente patogeno|pathogen|viruela|smallpox|ebola|peste bubonica)\b", True),
    ],
    "VIOLENCE": [
        (r"\b(glorif\w*|ensalz\w*)\b.{0,25}\b(violen\w*|odio|hatred|guerra|war|terroris\w*)", True),
        (r"\b(terroris\w*|terrorista|hit[- ]and[- ]run|atropellar y huir|violent crimes?|crimen violento|delito violento)\b", True),
        (r"\b(poison\w*|envenen\w*|contaminat\w*|contamin\w*)\b.{0,40}\b(water supply|suministro de agua|agua potable|reservoir|food supply|comida de|alimentos de)", False),
        (r"\b(incendio|fuego|fire)\b.{0,30}\b(se propague|make it spread|spread quickly|propagarse rapido)", True),
        (r"\b(violen\w*|odio|hatred)\b.{0,20}\b(against|contra|towards|hacia)\b.{0,30}\b(civil\w*|minor\w*|women|mujeres|group|grupo|individual|people|personas|gente)", True),
        (r"\b(matar|mato|matarlo|matarla|asesinar|asesino a|envenen\w*|apunal\w*|acuchill\w*|estrangul\w*|tortur\w*|secuestr\w*|golpe\w*|lastimar|herir|danar|hacerle dano|disparar|dispararle|atropellar|ahogar|quemar|mutilar|"
         r"kill|murder|assassinate|poison|stab|strangle|torture|kidnap|abduct|beat up|hurt|injure|harm|shoot|run over|drown|maim|attack|assault)\b.{0,30}\b" + PERSON, True),
        (r"\b(tiroteo|masacre|ataque terrorista|atentado|mass shooting|school shooting|massacre|terrorist attack|terror attack|bombing|genocidio|genocide|limpieza etnica|ethnic cleansing)\b", True),
        (r"\b(planear|planea|organizar|cometer|llevar a cabo|plan|organize|carry out|commit|execute)\b.{0,30}\b(ataque|asesinato|atentado|homicidio|attack|murder|assassination|homicide|shooting)\b", False),
        (r"\b(empuj\w*|lastim\w*|golpe\w*|danar|hacer dano|herir|ahog\w*|sacudir|abusar de|secuestr\w*|matar|quemar|envenen\w*|"
         r"push|hurt|harm|hit|beat|drown|shake|abuse|kidnap|kill|burn|poison|starve)\b.{0,25}\b(a |al |a la |a un |a una |a mi |my |a |the )?" + MINOR, True),
        (r"\b(provocar|iniciar|causar|empezar|set|start|cause)\b.{0,15}\b(incendio|fuego|fire|wildfire|incendio forestal)\b.{0,40}\b(sin que|without|culpen|caught|detected|bosque|forest|casa de|house of|edificio|building)", False),
        (r"\b(incendiar|prenderle fuego a|quemarle|set fire to|burn down)\b.{0,30}\b(casa|carro|coche|auto|negocio|escuela|iglesia|mezquita|sinagoga|house|car|business|school|church|mosque|synagogue|home)\b", True),
    ],
    "SELF_HARM": [
        (r"\b(cometer suicidio|commit suicide|suicidarse)\b", True),
        (r"\b(how to|como|formas? de|ways? to)\s+(self[- ]harm|autolesion\w*|cortarse|suicid\w*|hacerse dano)", False),
        (r"\b(suicidarme|matarme|quitarme la vida|acabar con mi vida|cortarme|autolesionarme|hacerme dano|lastimarme|ahorcarme|colgarme|tirarme de|dejar de vivir|"
         r"kill myself|end my life|take my (own )?life|commit suicide|hurt myself|cut myself|harm myself|hang myself|starve myself)\b", False),
        (r"\b(forma|formas|manera|metodo|metodos) (mas )?(rapida|facil|indolora|segura|efectiva|sencilla)? ?(de|para) (morir|suicidarse|suicidarme|quitarse la vida|matarse)\b", False),
        (r"\b(painless|quick|easy|easiest|fastest|best) (way|method)s? to (die|kill (myself|yourself|oneself)|commit suicide|end (it|my life))\b", False),
        (r"\b(cuantas|cuantos|how many) (pastillas|pildoras|tabletas|pills|tablets)\b.{0,40}\b(morir|matarme|sobredosis|die|overdose|kill)\b", False),
        (r"\b(alent|anim|incit|promov|promuev|glorific|encourag|promot|glorif|foment)\w*.{0,40}\b(suicidio|suicidarse|autolesion|anorexia|bulimia|trastornos? alimentici|suicide|self[- ]harm|eating disorders?|anorexia|bulimia)\b", False),
    ],
    "DRUGS": [
        (r"\b(drogas ilegales|illegal drugs|sustancias ilegales|illicit drugs|esteroides|steroids|performance[- ]enhancing drugs)\b", True),
        (r"\b(cocinar|sintetizar|fabricar|producir|preparar|cultivar|extraer|vender|traficar|pasar|contrabandear|distribuir|comprar|conseguir|"
         r"cook|synthesize|synthesise|make|produce|manufacture|prepare|grow|extract|sell|smuggle|traffic|distribute|buy|get|obtain|purchase)\b.{0,40}\b"
         r"(metanfetamina|meth|metanfetaminas|methamphetamine|cocaina|cocaine|crack|heroina|heroin|fentanilo|fentanyl|lsd|mdma|extasis|ecstasy|cristal|droga|drogas|narcoticos?|opio|opium|crack cocaine|ketamina|ketamine|ghb|drugs|illegal drugs|narcotics|controlled substances?|sustancias controladas)\b", True),
        (r"\b(metanfetamina|methamphetamine|meth|cocaina|cocaine|heroina|heroin|fentanilo|fentanyl|droga|drogas|drugs)\b.{0,40}\b(en casa|at home|paso a paso|step by step|sin receta|without (a )?prescription|por la aduana|through customs|across the border|por la frontera|sin que me atrapen|without getting caught)\b", False),
    ],
    "HATE": [
        (r"\b(deshumaniz\w*|dehumaniz\w*|opresion de|oppression of)\b", True),
        (r"\b(discurso de odio|hate speech|propaganda (racista|nazi|antisemita)|racist (joke|jokes|post|essay|speech|propaganda)|chistes? racistas?|chistes? sobre (negros|judios|gays|indigenas|mexicanos)|white supremac|supremacia blanca)\b", True),
        (r"\b(grupos? minoritarios?|minority groups?|ciertos grupos|certain groups|judios|judio|jews|jewish people|musulmanes|muslims|negros|black people|blacks|indigenas|indios|gays|homosexuales|lesbianas|trans|transgenero|transgender|mujeres|women|inmigrantes|immigrants|migrantes|mexicanos|mexicans|latinos|asiaticos|asians|gitanos|arabes|arabs|cristianos|christians|hindus|chinos|chinese|refugiados|refugees|discapacitados|disabled people)\b"
         r".{0,40}\b(son|are|es|is)\b.{0,15}\b(inferiores|inferior|subhumanos|subhuman|animales|animals|parasitos|parasites|vermin|plaga|basura|trash|ratas|rats|una enfermedad|a disease|criminales por naturaleza)\b", False),
        (r"\b(exterminar|eliminar|expulsar|deportar a todos|aniquilar|exterminate|wipe out|eliminate|annihilate|get rid of)\b.{0,30}\b(los |las |all |the )?(judios|jews|musulmanes|muslims|negros|black people|indigenas|gays|homosexuales|trans|inmigrantes|immigrants|migrantes|mexicanos|mexicans|gitanos|arabes|refugiados|refugees)\b", False),
        (r"\b(holocausto (no existio|nunca ocurrio|es (un )?mentira)|holocaust (never happened|didn'?t happen|is a (lie|hoax|myth))|holocaust denial)\b", False),
        (r"\b(incite|incitar|promote|promover|fomentar|encourage)\b.{0,30}\b(hatred|odio|violence against|violencia contra|discrimination|discriminacion|racism|racismo)\b", False),
    ],
    "HARASSMENT": [
        (r"\b(acos|hostig|amenaz|intimid|humill|chantaj|extorsion|aterroriz|doxe|"
         r"harass|stalk|threaten|intimidat|bull(y|ies|ied)|cyberbull|humiliat|blackmail|extort|terroriz|doxx?)\w*\b.{0,40}\b" + PERSON, True),
        (r"\b(mensajes?|cartas?|correos?|posts?|messages?|letters?|emails?|texts?|comments?)\b.{0,20}\b(para|de|to|that|which)\b.{0,10}\b(acosar|amenazar|intimidar|humillar|harass|threaten|intimidate|bully|humiliate|scare)\b", True),
        (r"\b(difundir|publicar|compartir|subir|filtrar|share|post|leak|distribute|spread)\b.{0,30}\b(fotos intimas|fotos desnud|videos intimos|nudes|nude (photos|pictures|images)|intimate (photos|images|videos)|sexual (photos|images|videos)|revenge porn)\b", False),
        (r"\b(rastrear|espiar|vigilar|seguir|localizar|track|spy on|monitor|follow|locate)\b.{0,40}\b(celular|telefono|ubicacion|mensajes|phone|location|messages|whereabouts)\b.{0,30}\b(sin que|sin su|without (her|his|their|them)|secretly|en secreto|a escondidas)", False),
        (r"\b(rastrear|espiar|track|spy on|stalk)\b.{0,10}\b(a )?(mi |my )?(novia|novio|esposa|esposo|ex|pareja|girlfriend|boyfriend|wife|husband|partner|ex)\b", False),
        (r"\b(direccion|domicilio|telefono personal|numero de telefono|home address|phone number|personal (information|details)|datos personales)\b.{0,40}\b(de (esta |este |la |el )?(actriz|actor|cantante|periodista|persona|mujer|influencer|celebridad|politico)|of (this |the |a )?(actress|actor|singer|journalist|person|woman|celebrity|politician|private (citizen|individual)))", True),
    ],
    "SEXUAL_MINORS": [
        (r"\b(pornografia infantil|abuso sexual infantil|material de abuso sexual infantil|child porn|child pornography|child sexual abuse material|csam|pedofil|pedophil|lolicon)\b", True),
        (r"\b(sexual|sexuales|sexo|erotic[ao]?|erotica|desnud[oa]s?|nudes?|naked|porn|porno|pornografic[oa]|intim[oa]s?|seducir|seduce|grooming|lewd|explicit)\b.{0,50}" + MINOR, False),
        (MINOR + r".{0,50}\b(sexual|sexuales|sexo|erotic[ao]?|erotica|desnud[oa]s?|nudes?|naked|porn|porno|explicit|lewd)\b", False),
        (r"\b(convencer|manipular|enganar|convince|persuade|groom|trick)\b.{0,30}" + MINOR + r".{0,40}\b(fotos|foto|desnud|enviar|mandar|encontrarse|verse conmigo|photos|pictures|nude|send|meet)", False),
    ],
    "FRAUD_PRIVACY": [
        (r"\b(noticias? falsas?|articulos? de noticias falsos?|historias? de noticias falsas?|informacion erronea|conspirativ\w*|identidad falsa|fake identit\w*|sitio web falso|fake website)\b", True),
        (r"\b(commit\w*|cometer|perpetrar)\b.{0,20}\b(identity theft|robo de identidad|fraud\w*|fraude|insider trading|crimes?|crimen|delitos?|tax evasion|money laundering)", False),
        (r"\b(fake reviews?|resenas falsas|opiniones falsas|spam|social engineering|ingenieria social)\b", True),
        (r"\b(manipul\w*)\b.{0,30}\b(financial data|stock|market\w*|mercado|datos financieros|ratings|calificaciones)", True),
        (r"\b(collect\w*|recopil\w*|recolect\w*)\b.{0,30}\b(personal data|datos personales|user data|datos de usuarios)\b.{0,40}\b(without|sin)\b", False),
        (r"\b(illegally download|descargar ilegalmente|piratear|pirate|piracy|pirateria)\w*", True),
        (r"\b(evade|evadir|escape from|escapar de|huir de|outrun)\b.{0,20}\b(law enforcement|fuerzas del orden|the police|la policia|police|prison|jail|carcel|prision|correctional|las autoridades)", True),
        (r"\b(phishing|correo falso|correos falsos|fake (email|e-mail|login page|website)|pagina falsa|sitio falso|scam (email|message|call|script)|estafa)\b", True),
        (r"\b(clonar|clona|clone|cloning|skim|skimmer|skimming|carding)\b.{0,30}\b(tarjeta|tarjetas|card|cards)\b", False),
        (r"\b(lavar|blanquear|launder|laundering|lavado de)\b.{0,20}\b(dinero|money|fondos|funds|activos)\b", True),
        (r"\b(falsific\w*|forjar|forg\w*|counterfeit\w*|fake|falso|falsa|falsos)\b.{0,25}\b(pasaporte|pasaportes|documento|documentos|identificacion|ine|credencial|licencia|billetes|dinero|moneda|firma|receta|titulo|passport|passports|documents?|id|ids|identification|license|bills|money|currency|signature|prescription|diploma|cheque|check)\b", True),
        (r"\b(robar|robo de|suplantar|steal|stealing|theft of|impersonate)\b.{0,30}\b(identidad|identidades|identity|identities|datos personales|personal (data|information)|tarjetas? de credito|credit cards?|numeros? de tarjeta|bank (accounts?|details))\b", True),
        (r"\b(estaf\w*|defraud\w*|timar|enganar a|scam\w*|swindl\w*)\b.{0,30}\b(ancianos|abuelitos|personas mayores|clientes|inversionistas|gente|personas|elderly|seniors|old people|customers|investors|people|victims|victimas)\b", True),
        (r"\b(esquema ponzi|ponzi scheme|piramide financiera|pyramid scheme|insider trading|uso de informacion privilegiada|evadir impuestos|evasion fiscal|tax evasion|evade taxes|manipular el mercado|market manipulation|pump and dump)\b", True),
        (r"\b(noticias falsas|fake news|desinformacion|disinformation|misinformation|informacion falsa|false information|bulos?|hoax|propaganda|teorias? (de|de la) conspiracion|conspiracy theor)\b", True),
        (r"\b(robar|roba|steal|shoplift|shoplifting|rob|robbing|asaltar|hurtar|carjack)\b.{0,30}\b(tienda|banco|coche|carro|auto|casa|cajero|store|shop|bank|car|house|atm|walmart|target|someone|alguien|empleador|employer|empresa|company|cash|dinero|money|joyeria|jewelry)\b", True),
    ],
    "ILLEGAL_INTRUSION": [
        (r"\b(explot\w*|exploit\w*)\b.{0,20}\b(vulnerabilidad\w*|vulnerabilit\w*)", True),
        (r"\b(romper|descifrar|crackear|crack|break)\b.{0,20}\b(contrasenas?|passwords?|cifrado|encryption)", True),
        (r"\b(ataques? cibernetic\w*|evitar (las )?medidas de seguridad|bases? de datos (del )?gobierno\w*|secuestr\w* (el|la) (sistema|cuenta|control))", True),
        (r"\b(rob[ae]r?|robe|robo de)\b.{0,25}\b(datos|informacion|credenciales|contrasenas)\b", True),
        (r"\b(cyber ?attacks?|ciberataques?|hijack\w*|infiltrat\w*|infiltrar\w*)\b", True),
        (r"\b(virus|gusano|worm)\b.{0,40}\b(infect\w*|infectar|computer|computadora|network|red|system|sistema|files|archivos|data|datos|spread|propag\w*|destroy\w*|damage|danar|disable\w*)", True),
        (r"\b(steal\w*|rob\w*)\b.{0,20}\b(sensitive|personal|user|private|confidential|personales|privad\w*)\b.{0,10}\b(data|information|datos|informacion)", True),
        (r"\b(hackear|hackea|hackeo|hack|hacking|hack into|crackear|crack|vulnerar|irrumpir|break into|breach|compromise)\b.{0,40}\b(cuenta|cuentas|correo|wifi|red|redes|servidor|servidores|sistema|sistemas|pagina|sitio|web|celular|telefono|base de datos|banco|gobierno|account|accounts|email|wi-?fi|network|networks|server|servers|system|systems|website|site|phone|database|databases|bank|government|computer|computers|device|devices|password|passwords|contrasena|contrasenas|camera|camara|infrastructure|grid|hospital)\b", False),
        (r"\b(entrar|acceder|meterme|ingresar|access|get into|log ?in(to)?|break into)\b.{0,30}\b(cuenta|correo|computadora|telefono|celular|facebook|instagram|whatsapp|account|email|computer|phone|facebook|instagram|whatsapp|icloud|gmail)\b.{0,30}\b(de otra persona|de alguien|de mi ex|de mi novi[ao]|ajena|someone else'?s|another person'?s|my ex'?s|sin (su )?(permiso|contrasena|autorizacion)|without (their|his|her|the owner'?s)? ?(permission|password|authorization|knowledge|consent))", False),
        (r"\b(malware|ransomware|keylogger|botnet|troyano|trojan|spyware|rootkit|virus informatico|computer virus|gusano informatico|worm|ddos|denial of service|exploit|exploits|zero[- ]day|backdoor|puerta trasera|rat)\b", True),
        (r"\b(bypass|evadir|evade|eludir|saltarse|circumvent|disable|desactivar|crack)\b.{0,30}\b(seguridad|antivirus|firewall|autenticacion|contrasena|2fa|captcha|drm|licencia|deteccion|security|authentication|password|detection|paywall|license|copy protection|parental controls|controles parentales)\b", True),
        (r"\b(robar|roba|obtener|sacar|extraer|steal|harvest|exfiltrate|grab|scrape|dump)\b.{0,30}\b(contrasenas|contrasena|credenciales|passwords|password|credentials|login|cookies de sesion|session cookies|tokens?|datos sensibles|sensitive (data|information)|informacion confidencial|confidential (data|information))\b", True),
        (r"\b(inyeccion sql|sql injection|xss|cross[- ]site scripting|fuerza bruta|brute[- ]force|credential stuffing|man[- ]in[- ]the[- ]middle)\b", True),
    ],
    # Categoría para patrones aprendidos por el DGM (la lista base está vacía).
    "LEARNED_PATTERN": [],
}

SELF_HARM_SUPPORT = (
    "Parece que estás pasando por algo muy difícil. No estás solo/a. En México puedes llamar "
    "gratis a la Línea de la Vida 800 911 2000 (24 h) o al 911 si estás en peligro inmediato."
)

# Contextos de ayuda/prevención que desactivan reglas que requieren señal operativa.
PROTECTIVE = re.compile(
    r"\b(prevenir|prevencion|proteger|protegerme|protegerlos|denunciar|como detectar|reconocer las senales|ayudar a (un|una|mi) |que hago si|historia de|por que|que es|que fue|como funciona|capacitar|concientizar|"
    r"prevent|prevention|protect|how to detect|recognize the signs|defend against|help (a|my) (friend|child)|what should i do if|stay safe|history of|how (does|do) [a-z ]{1,30} work|train (my|our) (team|staff|employees)|awareness|why (are|is|was|were|did|do)|what (is|was|were) the)\b"
)


@dataclass
class FirewallConfig:
    ruleset: str = "bilingual"  # "bilingual" | "legacy_cyber"


def _scan(text: str, ruleset: str, learned=()) -> list[dict]:
    folded = fold(text)
    violations: list[dict] = []
    if ruleset == "legacy_cyber":
        for category, patterns in LEGACY_RULES.items():
            for pattern in patterns:
                m = re.search(pattern, folded)
                if m:
                    violations.append({"category": category, "match": m.group(0)})
                    break
        return violations
    has_cue = re.search(CUE, folded) is not None
    protective = PROTECTIVE.search(folded) is not None
    for category, rules in HARM_RULES.items():
        for pattern, needs_cue in rules:
            m = re.search(pattern, folded)
            if not m:
                continue
            if needs_cue and (not has_cue or protective):
                continue
            violations.append({"category": category, "match": m.group(0)[:80]})
            break
    # Patrones APRENDIDOS (motor mutable): solo pueden AGREGAR bloqueos y exigen señal operativa.
    if not violations and has_cue and not protective:
        for category, keyword in learned:
            if re.search(r"\b" + re.escape(fold(keyword)) + r"\b", folded):
                violations.append({"category": category, "match": keyword, "learned": True})
                break
    return violations


def validate(instruction: dict, config: FirewallConfig | None = None, learned=()) -> dict:
    """Valida la instrucción formal (petición) y CUARENTENA los datos externos marcados.

    - Una violación en la petición del usuario BLOQUEA.
    - Una violación en `external_data` NO se ejecuta como instrucción: ese fragmento se
      pone en cuarentena (se elimina del contexto que verá el equipo) y queda auditado.
      Si los datos externos traen inyección, el ciclo sigue solo con datos limpios.
    """
    config = config or FirewallConfig()
    errors: list[str] = []
    objective = instruction.get("objective")
    if not isinstance(objective, str):
        errors.append("INVALID_OBJECTIVE")
    elif not objective.strip():
        errors.append("EMPTY_OBJECTIVE")
    elif len(objective) > MAX_INPUT:
        errors.append("INPUT_LIMIT_EXCEEDED")
    if not isinstance(instruction.get("constraints"), list):
        errors.append("INVALID_CONSTRAINTS")
    if not isinstance(instruction.get("external_data", []), list):
        errors.append("INVALID_EXTERNAL_DATA")

    violations = _scan(objective, config.ruleset, learned) if not errors else []
    clean_external, quarantined = [], []
    for i, item in enumerate(instruction.get("external_data", []) if not errors else []):
        text = item.get("text", "") if isinstance(item, dict) else str(item)
        found = _scan(text, config.ruleset, learned)
        if found:
            quarantined.append({"index": i, "violations": found})
        else:
            clean_external.append(item)

    return {
        "layer": "L2_SEMANTIC_FIREWALL",
        "method": f"rules:{config.ruleset}",
        "allowed": not errors and not violations,
        "errors": errors,
        "violations": violations,
        "categories": sorted({v["category"] for v in violations}),
        "self_harm": any(v["category"] == "SELF_HARM" for v in violations),
        "external_clean": clean_external,
        "external_quarantined": quarantined,
    }


def scan_text(text: str, ruleset: str = "bilingual", learned=()) -> list[dict]:
    """Escaneo directo (se usa también sobre la SALIDA del equipo)."""
    return _scan(text, ruleset, learned)
