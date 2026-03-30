// ---------------------------------------------------------------------------
// Content Machine — Caption Generator for CollectAI
// Generates multilingual captions in organic + commerce modes
// Full templates for all 9 pillars × 6 languages × 2 modes
// ---------------------------------------------------------------------------

import type {
  ContentIdea,
  GeneratedCaption,
  CaptionPack,
  LanguageCode,
} from "./types";
import { LANGUAGES } from "./types";

// ─── Caption templates per pillar × language × mode ──────────────────────

type LangCaptions = { organic: string[]; commerce: string[] };
type CaptionTemplates = Record<string, Record<LanguageCode, LangCaptions>>;

// Helper: builds a full 6-lang entry from EN + translations
function langEntry(
  en: LangCaptions, nl: LangCaptions, de: LangCaptions,
  fr: LangCaptions, es: LangCaptions, it: LangCaptions,
): Record<LanguageCode, LangCaptions> {
  return { en, nl, de, fr, es, it };
}

const TEMPLATES: CaptionTemplates = {
  // ─── Market Alert ────────────────────────────────────────────
  "market-alert": langEntry(
    { organic: [
        "{KEYWORD} prices just shifted. Here's what you need to know.",
        "Market alert: {KEYWORD} is on the move. Collectors, pay attention.",
        "This {KEYWORD} was underpriced. Not anymore.",
      ], commerce: [
        "Track {KEYWORD} prices in real time with CollectAI. Link in bio.",
        "{KEYWORD} price alert. Get notified before everyone else — download CollectAI.",
      ] },
    { organic: [
        "{KEYWORD} prijzen bewegen. Dit moet je weten.",
        "Marktupdate: {KEYWORD} gaat hard. Opletten.",
        "{KEYWORD} was ondergewaardeerd. Niet meer.",
      ], commerce: [
        "Volg {KEYWORD} prijzen in real time met CollectAI. Link in bio.",
        "{KEYWORD} alert. Wees er eerder bij — download CollectAI.",
      ] },
    { organic: [
        "{KEYWORD} Preise bewegen sich. Das musst du wissen.",
        "Markt-Alert: {KEYWORD} verändert sich gerade. Aufpassen.",
        "{KEYWORD} war unterbewertet. Nicht mehr.",
      ], commerce: [
        "Verfolge {KEYWORD} Preise in Echtzeit mit CollectAI. Link in Bio.",
        "{KEYWORD} Preisalarm. Erfahre es vor allen anderen — lade CollectAI.",
      ] },
    { organic: [
        "Les prix {KEYWORD} bougent. Voici ce qu'il faut savoir.",
        "Alerte marché : {KEYWORD} en mouvement. Collectionneurs, attention.",
        "{KEYWORD} était sous-évalué. Plus maintenant.",
      ], commerce: [
        "Suivez les prix {KEYWORD} en temps réel avec CollectAI. Lien en bio.",
        "Alerte prix {KEYWORD}. Soyez informé avant tout le monde — téléchargez CollectAI.",
      ] },
    { organic: [
        "Los precios de {KEYWORD} se están moviendo. Esto es lo que necesitas saber.",
        "Alerta de mercado: {KEYWORD} en movimiento. Coleccionistas, atentos.",
        "{KEYWORD} estaba infravalorado. Ya no más.",
      ], commerce: [
        "Rastrea precios de {KEYWORD} en tiempo real con CollectAI. Link en bio.",
        "Alerta de precio {KEYWORD}. Entérate antes que nadie — descarga CollectAI.",
      ] },
    { organic: [
        "I prezzi di {KEYWORD} si stanno muovendo. Ecco cosa devi sapere.",
        "Allerta mercato: {KEYWORD} in movimento. Collezionisti, attenzione.",
        "{KEYWORD} era sottovalutato. Non più.",
      ], commerce: [
        "Monitora i prezzi di {KEYWORD} in tempo reale con CollectAI. Link in bio.",
        "Allerta prezzo {KEYWORD}. Scoprilo prima di tutti — scarica CollectAI.",
      ] },
  ),

  // ─── Deal Hunting ────────────────────────────────────────────
  "deal-hunting": langEntry(
    { organic: [
        "Found this {KEYWORD} for almost nothing. The real value? Way more.",
        "The best {KEYWORD} deals are hiding in plain sight. Here's proof.",
        "I never pay full price for {KEYWORD}. This is how.",
      ], commerce: [
        "Scan any find to know its real value instantly. CollectAI — link in bio.",
        "Never overpay for {KEYWORD} again. CollectAI shows you the real market price.",
      ] },
    { organic: [
        "Dit {KEYWORD} vond ik voor bijna niks. De echte waarde? Veel meer.",
        "De beste {KEYWORD} deals liggen overal. Hier is het bewijs.",
        "Ik betaal nooit de volle prijs voor {KEYWORD}. Zo doe ik het.",
      ], commerce: [
        "Scan elke vondst voor de echte waarde. CollectAI — link in bio.",
        "Nooit meer te veel betalen voor {KEYWORD}. CollectAI toont de marktprijs.",
      ] },
    { organic: [
        "Dieses {KEYWORD} habe ich fast geschenkt bekommen. Der echte Wert? Deutlich mehr.",
        "Die besten {KEYWORD} Deals sind direkt vor dir. Hier ist der Beweis.",
        "Ich zahle nie den vollen Preis für {KEYWORD}. So mache ich das.",
      ], commerce: [
        "Scanne jeden Fund für den echten Wert. CollectAI — Link in Bio.",
        "Nie wieder zu viel für {KEYWORD} zahlen. CollectAI zeigt den Marktpreis.",
      ] },
    { organic: [
        "J'ai trouvé ce {KEYWORD} pour presque rien. La vraie valeur ? Bien plus.",
        "Les meilleures affaires {KEYWORD} sont sous tes yeux. Voici la preuve.",
        "Je ne paie jamais le prix fort pour {KEYWORD}. Voici comment.",
      ], commerce: [
        "Scannez n'importe quelle trouvaille pour sa vraie valeur. CollectAI — lien en bio.",
        "Ne surpayez plus jamais {KEYWORD}. CollectAI montre le vrai prix du marché.",
      ] },
    { organic: [
        "Encontré este {KEYWORD} por casi nada. El valor real? Mucho más.",
        "Las mejores ofertas de {KEYWORD} están a la vista. Aquí está la prueba.",
        "Nunca pago precio completo por {KEYWORD}. Así lo hago.",
      ], commerce: [
        "Escanea cualquier hallazgo para saber su valor real. CollectAI — link en bio.",
        "No pagues de más por {KEYWORD}. CollectAI muestra el precio real del mercado.",
      ] },
    { organic: [
        "Ho trovato questo {KEYWORD} per quasi niente. Il valore reale? Molto di più.",
        "Le migliori offerte {KEYWORD} sono sotto i tuoi occhi. Ecco la prova.",
        "Non pago mai il prezzo pieno per {KEYWORD}. Ecco come faccio.",
      ], commerce: [
        "Scansiona qualsiasi trova per il valore reale. CollectAI — link in bio.",
        "Non pagare troppo per {KEYWORD}. CollectAI mostra il prezzo di mercato reale.",
      ] },
  ),

  // ─── Collection Showcase ─────────────────────────────────────
  "collection-showcase": langEntry(
    { organic: [
        "Years of collecting {KEYWORD}. Every piece has a story.",
        "My {KEYWORD} collection in 60 seconds. Still growing.",
        "People ask how much my {KEYWORD} collection is worth. Let me show you.",
      ], commerce: [
        "Track your entire collection and see its real value. CollectAI — link in bio.",
        "Know exactly what your {KEYWORD} collection is worth. Download CollectAI free.",
      ] },
    { organic: [
        "Jaren {KEYWORD} verzamelen. Elk stuk heeft een verhaal.",
        "Mijn {KEYWORD} collectie in 60 seconden. Groeit nog steeds.",
        "Mensen vragen hoeveel mijn {KEYWORD} collectie waard is. Laat me het laten zien.",
      ], commerce: [
        "Track je hele collectie en zie de echte waarde. CollectAI — link in bio.",
        "Weet precies wat je {KEYWORD} collectie waard is. Download CollectAI gratis.",
      ] },
    { organic: [
        "Jahre des {KEYWORD} Sammelns. Jedes Stück hat eine Geschichte.",
        "Meine {KEYWORD} Sammlung in 60 Sekunden. Wächst immer noch.",
        "Leute fragen, was meine {KEYWORD} Sammlung wert ist. Ich zeig es euch.",
      ], commerce: [
        "Tracke deine gesamte Sammlung und sieh den echten Wert. CollectAI — Link in Bio.",
        "Wisse genau, was deine {KEYWORD} Sammlung wert ist. Lade CollectAI kostenlos.",
      ] },
    { organic: [
        "Des années à collectionner {KEYWORD}. Chaque pièce a une histoire.",
        "Ma collection {KEYWORD} en 60 secondes. Elle grandit encore.",
        "On me demande combien vaut ma collection {KEYWORD}. Laissez-moi vous montrer.",
      ], commerce: [
        "Suivez toute votre collection et voyez sa vraie valeur. CollectAI — lien en bio.",
        "Connaissez exactement la valeur de votre collection {KEYWORD}. Téléchargez CollectAI gratuit.",
      ] },
    { organic: [
        "Años coleccionando {KEYWORD}. Cada pieza tiene una historia.",
        "Mi colección de {KEYWORD} en 60 segundos. Sigue creciendo.",
        "La gente pregunta cuánto vale mi colección de {KEYWORD}. Déjame mostrarte.",
      ], commerce: [
        "Rastrea toda tu colección y ve su valor real. CollectAI — link en bio.",
        "Sabe exactamente cuánto vale tu colección de {KEYWORD}. Descarga CollectAI gratis.",
      ] },
    { organic: [
        "Anni a collezionare {KEYWORD}. Ogni pezzo ha una storia.",
        "La mia collezione {KEYWORD} in 60 secondi. Cresce ancora.",
        "Mi chiedono quanto vale la mia collezione {KEYWORD}. Ve lo mostro.",
      ], commerce: [
        "Traccia tutta la tua collezione e vedi il valore reale. CollectAI — link in bio.",
        "Sai esattamente quanto vale la tua collezione {KEYWORD}. Scarica CollectAI gratis.",
      ] },
  ),

  // ─── Grading Guide ──────────────────────────────────────────
  "grading-guide": langEntry(
    { organic: [
        "The difference between NM and LP on this {KEYWORD}? Hundreds.",
        "Is it real or fake? Here's how to tell with {KEYWORD}.",
        "One scratch. That's all it took to drop this {KEYWORD} by two grades.",
      ], commerce: [
        "Get an AI condition grade in seconds. CollectAI — link in bio.",
        "Stop guessing the grade. CollectAI scans and scores your {KEYWORD} instantly.",
      ] },
    { organic: [
        "Het verschil tussen NM en LP bij {KEYWORD}? Honderden euros.",
        "Echt of nep? Zo herken je het bij {KEYWORD}.",
        "Eén kras. Dat was genoeg om dit {KEYWORD} twee graden te laten zakken.",
      ], commerce: [
        "Krijg een AI-beoordeling in seconden. CollectAI — link in bio.",
        "Stop met raden. CollectAI scant en beoordeelt je {KEYWORD} direct.",
      ] },
    { organic: [
        "Der Unterschied zwischen NM und LP bei {KEYWORD}? Hunderte Euro.",
        "Echt oder Fälschung? So erkennst du es bei {KEYWORD}.",
        "Ein Kratzer. Das reichte, um dieses {KEYWORD} um zwei Grade zu senken.",
      ], commerce: [
        "Erhalte eine KI-Bewertung in Sekunden. CollectAI — Link in Bio.",
        "Schluss mit Raten. CollectAI scannt und bewertet dein {KEYWORD} sofort.",
      ] },
    { organic: [
        "La différence entre NM et LP pour ce {KEYWORD} ? Des centaines.",
        "Vrai ou faux ? Voici comment savoir avec {KEYWORD}.",
        "Une rayure. C'est tout ce qu'il a fallu pour perdre deux grades sur ce {KEYWORD}.",
      ], commerce: [
        "Obtenez un grade IA en secondes. CollectAI — lien en bio.",
        "Arrêtez de deviner le grade. CollectAI scanne et note votre {KEYWORD} instantanément.",
      ] },
    { organic: [
        "La diferencia entre NM y LP en este {KEYWORD}? Cientos de euros.",
        "¿Real o falso? Así se distingue con {KEYWORD}.",
        "Un rasguño. Eso fue suficiente para bajar este {KEYWORD} dos grados.",
      ], commerce: [
        "Obtén un grado IA en segundos. CollectAI — link en bio.",
        "Deja de adivinar el grado. CollectAI escanea y evalúa tu {KEYWORD} al instante.",
      ] },
    { organic: [
        "La differenza tra NM e LP per questo {KEYWORD}? Centinaia di euro.",
        "Vero o falso? Ecco come capirlo con {KEYWORD}.",
        "Un graffio. Bastato per far scendere questo {KEYWORD} di due gradi.",
      ], commerce: [
        "Ottieni un grado IA in pochi secondi. CollectAI — link in bio.",
        "Basta indovinare il grado. CollectAI scansiona e valuta il tuo {KEYWORD} istantaneamente.",
      ] },
  ),

  // ─── Unboxing & Reveal ──────────────────────────────────────
  "unboxing-reveal": langEntry(
    { organic: [
        "Opening this {KEYWORD} package. No idea what's inside.",
        "Mail day. Let's see if this {KEYWORD} was worth the wait.",
        "This {KEYWORD} was sealed for years. Time to open it.",
      ], commerce: [
        "Scanned it the second I opened it. CollectAI told me the value. Link in bio.",
        "Unbox, scan, know the value. That's the CollectAI workflow. Download free.",
      ] },
    { organic: [
        "Dit {KEYWORD} pakket openmaken. Geen idee wat erin zit.",
        "Postdag. Laten we kijken of dit {KEYWORD} het wachten waard was.",
        "Dit {KEYWORD} was jarenlang verzegeld. Tijd om het te openen.",
      ], commerce: [
        "Direct gescand na het openen. CollectAI gaf de waarde. Link in bio.",
        "Uitpakken, scannen, waarde weten. De CollectAI workflow. Gratis downloaden.",
      ] },
    { organic: [
        "Dieses {KEYWORD} Paket öffnen. Keine Ahnung, was drin ist.",
        "Posttag. Mal sehen, ob dieses {KEYWORD} das Warten wert war.",
        "Dieses {KEYWORD} war jahrelang versiegelt. Zeit, es zu öffnen.",
      ], commerce: [
        "Sofort nach dem Öffnen gescannt. CollectAI zeigte den Wert. Link in Bio.",
        "Auspacken, scannen, Wert kennen. Der CollectAI Workflow. Kostenlos laden.",
      ] },
    { organic: [
        "J'ouvre ce colis {KEYWORD}. Aucune idée de ce qu'il y a dedans.",
        "Jour de courrier. Voyons si ce {KEYWORD} valait l'attente.",
        "Ce {KEYWORD} était scellé depuis des années. Il est temps de l'ouvrir.",
      ], commerce: [
        "Scanné dès l'ouverture. CollectAI m'a donné la valeur. Lien en bio.",
        "Déballer, scanner, connaître la valeur. Le workflow CollectAI. Téléchargement gratuit.",
      ] },
    { organic: [
        "Abriendo este paquete de {KEYWORD}. Sin idea de lo que hay dentro.",
        "Día de correo. Veamos si este {KEYWORD} valió la espera.",
        "Este {KEYWORD} estaba sellado por años. Es hora de abrirlo.",
      ], commerce: [
        "Lo escaneé al segundo de abrirlo. CollectAI me dijo el valor. Link en bio.",
        "Abrir, escanear, saber el valor. El flujo de CollectAI. Descarga gratis.",
      ] },
    { organic: [
        "Apro questo pacco {KEYWORD}. Nessuna idea di cosa ci sia dentro.",
        "Giorno di posta. Vediamo se questo {KEYWORD} valeva l'attesa.",
        "Questo {KEYWORD} era sigillato da anni. È ora di aprirlo.",
      ], commerce: [
        "Scansionato appena aperto. CollectAI mi ha detto il valore. Link in bio.",
        "Apri, scansiona, conosci il valore. Il workflow CollectAI. Scarica gratis.",
      ] },
  ),

  // ─── Price Prediction ───────────────────────────────────────
  "price-prediction": langEntry(
    { organic: [
        "The data says {KEYWORD} is about to move. Here's the trend.",
        "Everyone is sleeping on {KEYWORD}. The numbers don't lie.",
        "I asked the ML model about {KEYWORD}. The prediction surprised me.",
      ], commerce: [
        "CollectAI predicts prices using machine learning. See where {KEYWORD} is heading. Link in bio.",
        "Data-driven price predictions for {KEYWORD}. Only on CollectAI.",
      ] },
    { organic: [
        "De data zegt dat {KEYWORD} gaat bewegen. Hier is de trend.",
        "Iedereen slaapt op {KEYWORD}. De cijfers liegen niet.",
        "Ik vroeg het ML-model over {KEYWORD}. De voorspelling verraste me.",
      ], commerce: [
        "CollectAI voorspelt prijzen met machine learning. Kijk waar {KEYWORD} naartoe gaat. Link in bio.",
        "Data-gedreven prijsvoorspellingen voor {KEYWORD}. Alleen op CollectAI.",
      ] },
    { organic: [
        "Die Daten sagen, {KEYWORD} wird sich bewegen. Hier ist der Trend.",
        "Alle schlafen bei {KEYWORD}. Die Zahlen lügen nicht.",
        "Ich habe das ML-Modell zu {KEYWORD} gefragt. Die Vorhersage überraschte mich.",
      ], commerce: [
        "CollectAI prognostiziert Preise mit Machine Learning. Sieh, wohin {KEYWORD} geht. Link in Bio.",
        "Datenbasierte Preisprognosen für {KEYWORD}. Nur bei CollectAI.",
      ] },
    { organic: [
        "Les données disent que {KEYWORD} va bouger. Voici la tendance.",
        "Tout le monde dort sur {KEYWORD}. Les chiffres ne mentent pas.",
        "J'ai demandé au modèle ML pour {KEYWORD}. La prédiction m'a surpris.",
      ], commerce: [
        "CollectAI prédit les prix avec le machine learning. Voyez où va {KEYWORD}. Lien en bio.",
        "Prédictions de prix basées sur les données pour {KEYWORD}. Uniquement sur CollectAI.",
      ] },
    { organic: [
        "Los datos dicen que {KEYWORD} va a moverse. Aquí está la tendencia.",
        "Todos duermen con {KEYWORD}. Los números no mienten.",
        "Le pregunté al modelo ML sobre {KEYWORD}. La predicción me sorprendió.",
      ], commerce: [
        "CollectAI predice precios con machine learning. Mira hacia dónde va {KEYWORD}. Link en bio.",
        "Predicciones de precios basadas en datos para {KEYWORD}. Solo en CollectAI.",
      ] },
    { organic: [
        "I dati dicono che {KEYWORD} si muoverà. Ecco il trend.",
        "Tutti dormono su {KEYWORD}. I numeri non mentono.",
        "Ho chiesto al modello ML su {KEYWORD}. La previsione mi ha sorpreso.",
      ], commerce: [
        "CollectAI prevede i prezzi con il machine learning. Guarda dove va {KEYWORD}. Link in bio.",
        "Previsioni di prezzo basate sui dati per {KEYWORD}. Solo su CollectAI.",
      ] },
  ),

  // ─── Beginner Guide ─────────────────────────────────────────
  "beginner-guide": langEntry(
    { organic: [
        "New to {KEYWORD}? Start here. No gatekeeping.",
        "The 3 things I wish I knew before collecting {KEYWORD}.",
        "Beginner {KEYWORD} mistakes that cost real money. Avoid these.",
      ], commerce: [
        "Start your collection the smart way. CollectAI helps beginners avoid costly mistakes. Link in bio.",
        "New collector? CollectAI scans and values {KEYWORD} so you buy smart. Download free.",
      ] },
    { organic: [
        "Nieuw met {KEYWORD}? Begin hier. Geen gatekeeping.",
        "De 3 dingen die ik wilde weten voordat ik {KEYWORD} ging verzamelen.",
        "Beginnersfouten met {KEYWORD} die echt geld kosten. Vermijd deze.",
      ], commerce: [
        "Begin slim met je collectie. CollectAI helpt beginners dure fouten te vermijden. Link in bio.",
        "Nieuwe verzamelaar? CollectAI scant en waardeert {KEYWORD} zodat je slim koopt. Gratis downloaden.",
      ] },
    { organic: [
        "Neu bei {KEYWORD}? Fang hier an. Kein Gatekeeping.",
        "Die 3 Dinge, die ich vor dem {KEYWORD} Sammeln gerne gewusst hätte.",
        "{KEYWORD} Anfängerfehler, die echtes Geld kosten. Vermeide diese.",
      ], commerce: [
        "Starte deine Sammlung smart. CollectAI hilft Anfängern, teure Fehler zu vermeiden. Link in Bio.",
        "Neuer Sammler? CollectAI scannt und bewertet {KEYWORD}, damit du smart kaufst. Kostenlos laden.",
      ] },
    { organic: [
        "Nouveau dans {KEYWORD} ? Commencez ici. Pas de gatekeeping.",
        "Les 3 choses que j'aurais voulu savoir avant de collectionner {KEYWORD}.",
        "Erreurs de débutant {KEYWORD} qui coûtent vraiment cher. Évitez-les.",
      ], commerce: [
        "Commencez votre collection intelligemment. CollectAI aide les débutants à éviter les erreurs coûteuses. Lien en bio.",
        "Nouveau collectionneur ? CollectAI scanne et évalue {KEYWORD} pour acheter malin. Téléchargement gratuit.",
      ] },
    { organic: [
        "¿Nuevo en {KEYWORD}? Empieza aquí. Sin elitismo.",
        "Las 3 cosas que desearía haber sabido antes de coleccionar {KEYWORD}.",
        "Errores de principiante en {KEYWORD} que cuestan dinero real. Evítalos.",
      ], commerce: [
        "Empieza tu colección de forma inteligente. CollectAI ayuda a principiantes a evitar errores costosos. Link en bio.",
        "¿Coleccionista nuevo? CollectAI escanea y valora {KEYWORD} para comprar bien. Descarga gratis.",
      ] },
    { organic: [
        "Nuovo con {KEYWORD}? Inizia qui. Niente gatekeeping.",
        "Le 3 cose che avrei voluto sapere prima di collezionare {KEYWORD}.",
        "Errori da principiante con {KEYWORD} che costano soldi veri. Evitali.",
      ], commerce: [
        "Inizia la tua collezione in modo smart. CollectAI aiuta i principianti a evitare errori costosi. Link in bio.",
        "Nuovo collezionista? CollectAI scansiona e valuta {KEYWORD} per comprare bene. Scarica gratis.",
      ] },
  ),

  // ─── Collector Lifestyle ────────────────────────────────────
  "lifestyle-collector": langEntry(
    { organic: [
        "Saturday morning. Coffee. Shelves. {KEYWORD}.",
        "The display setup took 3 days. Every piece in its place.",
        "This is what a {KEYWORD} collection looks like when it's organized.",
      ], commerce: [
        "Organize your collection digitally. CollectAI keeps everything tracked. Link in bio.",
        "From shelf chaos to organized bliss. CollectAI helped me organize my {KEYWORD}.",
      ] },
    { organic: [
        "Zaterdagochtend. Koffie. Planken. {KEYWORD}.",
        "De display setup kostte 3 dagen. Elk stuk op zijn plek.",
        "Zo ziet een {KEYWORD} collectie eruit als het georganiseerd is.",
      ], commerce: [
        "Organiseer je collectie digitaal. CollectAI houdt alles bij. Link in bio.",
        "Van chaos naar overzicht. CollectAI hielp me mijn {KEYWORD} te organiseren.",
      ] },
    { organic: [
        "Samstagmorgen. Kaffee. Regale. {KEYWORD}.",
        "Das Display-Setup hat 3 Tage gedauert. Jedes Stück an seinem Platz.",
        "So sieht eine {KEYWORD} Sammlung aus, wenn sie organisiert ist.",
      ], commerce: [
        "Organisiere deine Sammlung digital. CollectAI trackt alles. Link in Bio.",
        "Vom Regalchaos zur Ordnung. CollectAI half mir, mein {KEYWORD} zu organisieren.",
      ] },
    { organic: [
        "Samedi matin. Café. Étagères. {KEYWORD}.",
        "L'installation du display a pris 3 jours. Chaque pièce à sa place.",
        "Voilà à quoi ressemble une collection {KEYWORD} quand elle est organisée.",
      ], commerce: [
        "Organisez votre collection numériquement. CollectAI garde tout suivi. Lien en bio.",
        "Du chaos à l'ordre. CollectAI m'a aidé à organiser mes {KEYWORD}.",
      ] },
    { organic: [
        "Sábado por la mañana. Café. Estantes. {KEYWORD}.",
        "Montar el display llevó 3 días. Cada pieza en su lugar.",
        "Así se ve una colección de {KEYWORD} cuando está organizada.",
      ], commerce: [
        "Organiza tu colección digitalmente. CollectAI lo rastrea todo. Link en bio.",
        "Del caos al orden. CollectAI me ayudó a organizar mis {KEYWORD}.",
      ] },
    { organic: [
        "Sabato mattina. Caffè. Scaffali. {KEYWORD}.",
        "Allestire il display ha richiesto 3 giorni. Ogni pezzo al suo posto.",
        "Ecco come appare una collezione {KEYWORD} quando è organizzata.",
      ], commerce: [
        "Organizza la tua collezione digitalmente. CollectAI tiene traccia di tutto. Link in bio.",
        "Dal caos all'ordine. CollectAI mi ha aiutato a organizzare i miei {KEYWORD}.",
      ] },
  ),

  // ─── App Feature ────────────────────────────────────────────
  "app-feature": langEntry(
    { organic: [
        "I scanned a random item and the AI knew everything about it.",
        "POV: you find something and need to know the price NOW.",
        "This app just told me my collection is worth more than I thought.",
      ], commerce: [
        "CollectAI — scan, track, and value your collectibles. Free download, link in bio.",
        "Your entire collection in one app. Real prices, AI grading, portfolio tracking. Download CollectAI.",
      ] },
    { organic: [
        "Ik scande een willekeurig item en de AI wist alles erover.",
        "POV: je vindt iets en moet NU de prijs weten.",
        "Deze app vertelde me dat mijn collectie meer waard is dan ik dacht.",
      ], commerce: [
        "CollectAI — scan, track en waardeer je collectie. Gratis download, link in bio.",
        "Je hele collectie in één app. Echte prijzen, AI grading, portfolio tracking. Download CollectAI.",
      ] },
    { organic: [
        "Ich habe ein zufälliges Item gescannt und die KI wusste alles darüber.",
        "POV: Du findest etwas und musst JETZT den Preis wissen.",
        "Diese App hat mir gesagt, dass meine Sammlung mehr wert ist als gedacht.",
      ], commerce: [
        "CollectAI — scanne, tracke und bewerte deine Sammlung. Kostenlos laden, Link in Bio.",
        "Deine ganze Sammlung in einer App. Echte Preise, KI-Grading, Portfolio-Tracking. Lade CollectAI.",
      ] },
    { organic: [
        "J'ai scanné un objet au hasard et l'IA savait tout dessus.",
        "POV : tu trouves quelque chose et tu dois connaître le prix MAINTENANT.",
        "Cette app m'a dit que ma collection vaut plus que je ne pensais.",
      ], commerce: [
        "CollectAI — scannez, suivez et évaluez vos objets de collection. Téléchargement gratuit, lien en bio.",
        "Toute votre collection dans une app. Vrais prix, grading IA, suivi de portfolio. Téléchargez CollectAI.",
      ] },
    { organic: [
        "Escaneé un artículo al azar y la IA sabía todo sobre él.",
        "POV: encuentras algo y necesitas saber el precio AHORA.",
        "Esta app me dijo que mi colección vale más de lo que pensaba.",
      ], commerce: [
        "CollectAI — escanea, rastrea y valora tus coleccionables. Descarga gratis, link en bio.",
        "Toda tu colección en una app. Precios reales, grading IA, seguimiento de portfolio. Descarga CollectAI.",
      ] },
    { organic: [
        "Ho scansionato un oggetto a caso e l'IA sapeva tutto.",
        "POV: trovi qualcosa e devi sapere il prezzo ORA.",
        "Questa app mi ha detto che la mia collezione vale più di quanto pensassi.",
      ], commerce: [
        "CollectAI — scansiona, traccia e valuta i tuoi oggetti da collezione. Download gratuito, link in bio.",
        "Tutta la tua collezione in un'app. Prezzi reali, grading IA, tracking portfolio. Scarica CollectAI.",
      ] },
  ),
};

// ─── Language-specific hashtags ──────────────────────────────────────────

const LOCALIZED_HASHTAGS: Record<LanguageCode, string[]> = {
  en: ["#collectibles", "#collector", "#collecting"],
  nl: ["#verzamelen", "#verzamelaar", "#collectie"],
  de: ["#sammeln", "#sammler", "#kollektion"],
  fr: ["#collection", "#collectionneur", "#collector"],
  es: ["#coleccion", "#coleccionista", "#coleccionar"],
  it: ["#collezione", "#collezionista", "#collezionismo"],
};

// ─── Pillar-specific hashtag boosts ──────────────────────────────────────

const PILLAR_HASHTAGS: Record<string, string[]> = {
  "market-alert": ["#PriceAlert", "#MarketUpdate"],
  "deal-hunting": ["#ThriftFind", "#DealHunter", "#GarageSaleFind"],
  "collection-showcase": ["#ShelfTour", "#CollectionGoals"],
  "grading-guide": ["#Grading", "#Authentication", "#ConditionMatters"],
  "unboxing-reveal": ["#Unboxing", "#MailDay", "#PackOpening"],
  "price-prediction": ["#PricePrediction", "#InvestInCollectibles"],
  "beginner-guide": ["#BeginnerCollector", "#CollectingTips"],
  "lifestyle-collector": ["#CollectorLifestyle", "#ShelfSetup"],
  "app-feature": ["#CollectAI", "#TechForCollectors"],
};

// ─── Helpers ─────────────────────────────────────────────────────────────

function pickRandom<T>(arr: T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function interpolate(template: string, keyword: string): string {
  return template.replace(/\{KEYWORD\}/g, keyword);
}

// ─── Single caption ──────────────────────────────────────────────────────

export function generateCaption(
  idea: ContentIdea,
  languageCode: LanguageCode
): GeneratedCaption {
  const pillarTemplates = TEMPLATES[idea.pillarSlug] ?? TEMPLATES["app-feature"];
  const langTemplates = pillarTemplates[languageCode] ?? pillarTemplates.en;

  const keyword = idea.targetKeyword ?? idea.nicheName ?? "collectibles";

  const organic = interpolate(pickRandom(langTemplates.organic), keyword);
  const commerce = interpolate(pickRandom(langTemplates.commerce), keyword);

  const localHashtags = LOCALIZED_HASHTAGS[languageCode] ?? LOCALIZED_HASHTAGS.en;
  const nicheHashtags = idea.hashtags.filter((h) => !h.startsWith("#Collect") && h !== "#CollectAI");
  const pillarTags = PILLAR_HASHTAGS[idea.pillarSlug] ?? [];
  const hashtags = [
    "#CollectAI",
    ...pillarTags.slice(0, 1),
    ...nicheHashtags.slice(0, 2),
    ...localHashtags.slice(0, 2),
  ].slice(0, 6);

  return {
    ideaId: idea.id,
    ideaTitle: idea.title,
    languageCode,
    organic,
    commerce,
    hashtags,
    seoKeyword: keyword,
  };
}

// ─── Caption pack (all languages for one idea) ──────────────────────────

export function generateCaptionPack(idea: ContentIdea): CaptionPack {
  const captions: CaptionPack["captions"] = {} as CaptionPack["captions"];

  for (const lang of LANGUAGES) {
    const caption = generateCaption(idea, lang);
    captions[lang] = {
      organic: caption.organic,
      commerce: caption.commerce,
      hashtags: caption.hashtags,
    };
  }

  return {
    ideaId: idea.id,
    ideaTitle: idea.title,
    hook: idea.hook,
    captions,
  };
}

// ─── Bulk generation ─────────────────────────────────────────────────────

export function generateCaptionPacks(ideas: ContentIdea[]): CaptionPack[] {
  return ideas.map(generateCaptionPack);
}

// ─── Markdown export ─────────────────────────────────────────────────────

export function exportCaptionsMarkdown(packs: CaptionPack[]): string {
  const lines: string[] = [
    "# Caption Packs",
    "",
    `Generated ${packs.length} packs × ${LANGUAGES.length} languages = ${packs.length * LANGUAGES.length} captions`,
    "",
  ];

  for (const pack of packs) {
    lines.push(`## ${pack.ideaTitle}`);
    lines.push(`> ${pack.hook}`);
    lines.push("");

    for (const lang of LANGUAGES) {
      const c = pack.captions[lang];
      lines.push(`### ${lang.toUpperCase()}`);
      lines.push(`**Organic:** ${c.organic}`);
      lines.push(`**Commerce:** ${c.commerce}`);
      lines.push(`**Hashtags:** ${c.hashtags.join(" ")}`);
      lines.push("");
    }
  }

  return lines.join("\n");
}
