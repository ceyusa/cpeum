#!/usr/bin/env node
/**
 * Genera un diff HTML (estilo diff2html/github) por cada reforma
 * constitucional representada en un commit, así como un índice de todas
 * las reformas.
 *
 * Para cada commit cuyo asunto comienza con "Artículo" o "Artículos"
 * se obtienen los archivos `.rst` modificados y se construye un diff
 * unificado usando el paquete `diff`. Ese diff se renderiza con
 * `diff2html` en su formato de líneas (outputFormat "line"), el mismo
 * aspecto que produce diff2html-cli.
 *
 * Salida:
 *   html/decretos/index.html       — índice de reformas (una por decreto)
 *   html/decretos/<numero>.html    — diff individual de cada decreto
 */

const { execSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { createPatch } = require("diff");
const { html: diff2html } = require("diff2html");

function htmlEscape(text) {
	return String(text).replace(/[&<>"']/g, (char) => {
		switch (char) {
			case "&":
				return "&amp;";
			case "<":
				return "&lt;";
			case ">":
				return "&gt;";
			case '"':
				return "&quot;";
			default:
				return "&#39;";
		}
	});
}

/* Convierte en vínculos las URLs del Diario Oficial de la Federación
   (dof.gob.mx). Recibe texto ya escapado con htmlEscape. */
function linkifyDof(text) {
	return text.replace(
		/(https?:\/\/[^\s<>"']*dof\.gob\.mx[^\s<>"']*)/g,
		'<a href="$1" rel="external noreferrer" target="_blank">$1</a>',
	);
}

const OUTDIR = path.resolve(__dirname, "..", "html", "decretos");
const DECRETOS_PATH = path.resolve(__dirname, "..", "html", "decretos.json");
const GIT_LOG_FORMAT = "%H%n%ci%n%s%n%b%n---END---";
const TITLE = "Decretos";

/* Hoja de estilo oficial de diff2html (la misma que usa diff2html-cli). */
const DIFF2HTML_CSS_PATH = require.resolve(
	"diff2html/bundles/css/diff2html.min.css",
);
const DIFF2HTML_CSS = fs.readFileSync(DIFF2HTML_CSS_PATH, "utf-8");

const GLOBAL_CSS = `\
body {
    font-family: Georgia, "Noto Serif", "DejaVu Serif", serif;
    max-width: 100ch;
    margin: 0 auto;
    padding: 40px 1.5em 1.5em;
    line-height: 1.8;
    font-size: 1.05em;
    color: #1a1a1a;
    background: #fafafa;
}
h1 { font-size: 1.3em; border-bottom: 2px solid #333; padding-bottom: 0.3em; }
h2 { font-size: 1.1em; margin-top: 1.5em; }
.reforma-nav {
    display: flex;
    justify-content: space-between;
    gap: 1em;
    margin: 0.5em 0 1em;
    font-size: 0.9em;
}
.reforma-nav a { color: #0066cc; text-decoration: none; }
.reforma-nav a:hover { text-decoration: underline; }
.reforma-nav .nav-disabled { color: #999; }
.reforma-nav .nav-prev { max-width: 45%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.reforma-nav .nav-next { text-align: right; }
.reforma-nav .nav-next a {
    display: inline-block;
    max-width: 45vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.commit-meta { color: #666; font-size: 0.9em; margin-bottom: 0.5em; }
.reforma-numero { color: #0066cc; font-size: 0.85em; margin: 0.1em 0 0.5em; }
.commit-meta a { color: #0066cc; text-decoration: none; }
.commit-meta a:hover { text-decoration: underline; }
.commit-body {
    white-space: pre-wrap;
    font-size: 0.9em;
    margin: 0.5em 0 1.5em 0;
    padding: 0.75em 1em;
    background: #f9f9f9;
    border-left: 3px solid #ccc;
    line-height: 1.5;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.commit-body a, .reforma-resumen a {
    color: #0066cc;
    text-decoration: none;
}
.commit-body a:hover, .reforma-resumen a:hover {
    text-decoration: underline;
}
.reforma { margin-bottom: 1.2em; }
.reforma-titulo { font-size: 1em; margin: 0.1em 0; }
.reforma-titulo a { color: #0066cc; text-decoration: none; }
.reforma-titulo a:hover { text-decoration: underline; }
.reforma-fecha { color: #666; font-size: 0.9em; }
.reforma-resumen {
    font-size: 1em;
    color: #555;
    margin: 0.2em 0 0 0;
}
.reforma-sep {
    border: none;
    border-top: 1px solid #d0d7de;
    margin: 1.2em 0 0 0;
}
/* Banner superior fijo, igual que en las páginas del sitio */
#top-banner {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 40px;
    background: #1a3a5c;
    color: #ffffff;
    display: flex;
    align-items: center;
    padding: 0 20px;
    box-sizing: border-box;
    z-index: 200;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
}
#top-banner .banner-link {
    color: #ffffff;
    text-decoration: none;
    font-size: 1.1em;
    font-weight: bold;
    letter-spacing: 0.05em;
}
#top-banner .banner-links {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 0.9em;
}
#top-banner .banner-icon {
    display: block;
    fill: currentColor;
}
#top-banner .banner-link:hover {
    text-decoration: underline;
}
#top-banner .banner-link:hover .banner-icon {
    opacity: 0.8;
}
.menu-toggle {
    display: none;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: #ffffff;
    cursor: pointer;
    padding: 4px;
    margin-right: 8px;
    line-height: 0;
}
.menu-toggle:hover {
    opacity: 0.8;
}
@media (max-width: 768px) {
    #top-banner {
        padding: 0 12px;
        gap: 4px;
    }
    #top-banner .banner-link {
        font-size: 1em;
    }
    /* Sin tabla de contenidos, la hamburguesa no se muestra */
    body:not(:has(nav.contents)) .menu-toggle {
        display: none;
    }
}
`;

const HTML_HEADER = `\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
${GLOBAL_CSS}
${DIFF2HTML_CSS}
</style>
`;

const FOOTER = `\
</body>
</html>
`;

const GITHUB_URL = "https://github.com/ceyusa/cpeum";

/* Banner superior, igual que el de index.html y acercade.html.
   Rutas relativas a html/decretos/index.html. */
const BANNER = `\
<div id="top-banner">
<button id="menu-toggle" class="menu-toggle" type="button" aria-label="Abrir menú" aria-expanded="false" aria-controls="contenido">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
<path d="M3 6h18v2H3zM3 11h18v2H3zM3 16h18v2H3z"/>
</svg>
</button>
<a class="banner-link" href="../index.html">CPEUM</a>
<div class="banner-links">
<a class="banner-link" href="index.html">Decretos</a>
<a class="banner-link" href="../acercade.html" title="Acerca del sitio">&#x1F6C8;</a>
<a class="banner-link" href="${GITHUB_URL}" title="Código fuente en GitHub">
<svg class="banner-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">
<path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
</svg>
</a>
</div>
</div>
`;

// ---------------------------------------------------------------------------
// Git helpers
// ---------------------------------------------------------------------------

function runGit(args) {
	return execSync(["git", ...args].join(" "), {
		encoding: "utf-8",
		timeout: 30000,
		stdio: ["ignore", "pipe", "pipe"],
	});
}

/** Devuelve los commits de decretos, en orden cronológico (antiguo → nuevo). */
function getReformaCommits() {
	const output = runGit([
		"log",
		"--reverse",
		"--grep=Artículo",
		"--grep=Articulo",
		"--grep=Artíclos",
		`--format=${GIT_LOG_FORMAT}`,
	]);
	const commits = [];
	for (const block of output.split("---END---")) {
		const trimmed = block.trim();
		if (!trimmed) continue;
		const lines = trimmed.split("\n");
		if (lines.length < 3) continue;
		const body = lines.slice(3).join("\n").trim();
		const pubDate = getPublicationDate(body);
		commits.push({
			hash: lines[0].trim(),
			date: lines[1].trim(),
			subject: lines[2].trim(),
			body,
			pubDate,
			iso: pubDateToIso(pubDate),
			decreto: getDecreeSummary(body),
		});
	}
	return commits;
}

/**
 * Carga y devuelve los decretos de decretos.json ordenados por número.
 * @returns {Array<{numero:number, decreto:string, publicacion:string}>}
 */
function loadDecretos() {
	const raw = fs.readFileSync(DECRETOS_PATH, "utf8");
	const decretos = JSON.parse(raw);
	decretos.sort((a, b) => a.numero - b.numero);
	return decretos;
}

/* Normaliza un texto para comparar títulos de decretos (ignora mayúsculas,
   acentos y espacios/puntuación). */
function normalizeText(text) {
	return String(text || "")
		.normalize("NFD")
		.replace(/[\u0300-\u036f]/g, "")
		.toLowerCase()
		.replace(/[^\p{L}\p{N}]+/gu, "");
}

/**
 * Relaciona los commits de reforma con los decretos de decretos.json y
 * devuelve la lista de reformas (una por decreto) en orden cronológico.
 *
 * El emparejamiento usa primero la fecha de publicación (DOF) y, si la
 * fecha no coincide, el título del decreto. Cada commit se asigna a un solo
 * decreto; los decretos sin commit quedan con `commits` vacío (faltan en
 * git). Se emiten avisos por discrepancias.
 *
 * @param {Array} decretos
 * @param {Array} commits
 * @returns {Array<*>}
 */
function buildReformas(decretos, commits) {
	const byTitle = new Map();
	for (const d of decretos) {
		const k = normalizeText(d.decreto);
		if (k && !byTitle.has(k)) byTitle.set(k, d);
	}
	const byDate = new Map();
	for (const d of decretos) {
		const arr = byDate.get(d.publicacion) || [];
		arr.push(d);
		byDate.set(d.publicacion, arr);
	}

	const used = new Set();
	const asignar = (commit, decreto) => {
		commit.numero = decreto.numero;
		commit.publicacion = decreto.publicacion;
		used.add(decreto.numero);
		if (decreto.publicacion !== commit.iso) {
			console.warn(
				`AVISO: el commit ${commit.hash.slice(0, 8)} "${commit.subject}" ` +
					`(fecha ${commit.iso}) no coincide con la fecha del decreto ` +
					`${decreto.numero} (${decreto.publicacion}).`,
			);
		}
	};

	// 1) Emparejamiento principal por fecha de publicación (DOF).
	const pendientes = [];
	for (const commit of commits) {
		const grupo = commit.iso ? byDate.get(commit.iso) : null;
		if (grupo) {
			const noUsados = grupo.filter((d) => !used.has(d.numero));
			const titulo = normalizeText(commit.decreto);
			let d = noUsados.find((x) => normalizeText(x.decreto) === titulo);
			if (!d) d = noUsados[0];
			if (d) {
				asignar(commit, d);
				continue;
			}
		}
		pendientes.push(commit);
	}

	// 2) Los commits sin fecha coincidente se vinculan por el título del decreto.
	for (const commit of pendientes) {
		const d = byTitle.get(normalizeText(commit.decreto));
		if (d && !used.has(d.numero)) {
			asignar(commit, d);
		} else {
			console.warn(
				`AVISO: el commit ${commit.hash.slice(0, 8)} "${commit.subject}" ` +
					"no corresponde a ningún decreto de decretos.json.",
			);
		}
	}

	const reformas = decretos.map((d) => ({
		numero: d.numero,
		decreto: d.decreto,
		publicacion: d.publicacion,
		commits: commits.filter((c) => c.numero === d.numero),
	}));

	for (const r of reformas) {
		if (r.commits.length > 1) {
			console.warn(
				`AVISO: el decreto ${r.numero} tiene ${r.commits.length} commits asociados.`,
			);
		}
	}

	return reformas;
}

/* Fecha de publicación en el DOF, extraída del cuerpo del commit.
   El año puede aparecer en la línea siguiente (el renglón de la fecha
   se parte en dos), por lo que se unen varias líneas antes de buscar. */
function getPublicationDate(body) {
	const lines = String(body).split("\n");
	const idx = lines.findIndex((line) =>
		/Publicado\s+en\s+el\s+Diario\s+Oficial/i.test(line),
	);
	if (idx < 0) return null;

	const joined = lines.slice(idx, idx + 3).join(" ");
	const datePattern =
		/(\d{1,2}(?:ro|º)?\.?\s+(?:de\s+)?[A-Za-záéíóúñü]+\s+(?:(?:de|del)\s+)?(?:año\s+)?\d{4})/i;
	const match = joined.match(datePattern);
	return match ? match[1].trim() : null;
}

/* Meses en español, igual que rst2html5.py. */
const SPANISH_MONTHS = {
	enero: 1,
	febrero: 2,
	marzo: 3,
	abril: 4,
	mayo: 5,
	junio: 6,
	julio: 7,
	agosto: 8,
	septiembre: 9,
	setiembre: 9,
	octubre: 10,
	noviembre: 11,
	diciembre: 12,
};

/* Convierte la fecha de publicación en español a ISO 8601 (YYYY-MM-DD),
   imitando pub_date_to_iso de rst2html5.py. Devuelve null si no se puede. */
function pubDateToIso(pubDate) {
	if (!pubDate || pubDate === "Sin fecha") return null;

	const match = String(pubDate)
		.trim()
		.match(
			/^(\d{1,2})(?:[roº]+)?\.?(?:\s+de)?\s+([A-Za-záéíóúñü]+)\s+(?:(?:de|del)\s+)?(?:año\s+)?(\d{3,4})$/i,
		);
	if (!match) return null;

	const day = Number(match[1]);
	const month = SPANISH_MONTHS[match[2].toLowerCase()];
	const year = Number(match[3]);

	if (!month || day < 1 || day > 31 || year < 1900) return null;

	return `${String(year).padStart(4, "0")}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

/* Resumen del decreto: el párrafo que comienza con DECRETO, REFORMA,
   REFORMAS, DECLARATORIA o LEY (el resumen puede ocupar varias líneas). */
function getDecreeSummary(body) {
	const paragraphs = String(body).split(/\n\s*\n/);
	for (const paragraph of paragraphs) {
		if (
			/^(?:DECRETO|REFORMA|REFORMAS|DECLARATORIA|LEY)\b/i.test(paragraph.trim())
		) {
			return paragraph.trim();
		}
	}
	return null;
}

/** Archivos .rst modificados por el commit dado. */
function getRstFiles(commitHash) {
	const output = runGit([
		"diff-tree",
		"--no-commit-id",
		"-r",
		"--name-only",
		commitHash,
	]);
	return output
		.trim()
		.split("\n")
		.filter((file) => file.endsWith(".rst") && file);
}

/** Contenido de un archivo en un commit dado (o "" si no existe). */
function getFileContent(commitHash, filepath) {
	try {
		return runGit(["show", `${commitHash}:${filepath}`]);
	} catch {
		return "";
	}
}

// ---------------------------------------------------------------------------
// Diff generation
// ---------------------------------------------------------------------------

function buildDiff(parentHash, commitHash, rstFile) {
	const oldContent = getFileContent(parentHash, rstFile);
	const newContent = getFileContent(commitHash, rstFile);
	if (oldContent === newContent) return "";

	const oldName = `${parentHash.slice(0, 8)}/${rstFile}`;
	const newName = `${commitHash.slice(0, 8)}/${rstFile}`;
	const patch = createPatch(rstFile, oldContent, newContent, oldName, newName);

	const htmlOutput = diff2html(patch, {
		drawFileList: false,
		matching: "none",
		outputFormat: "line",
		diffStyle: "word",
		fileContentToggle: false,
	});

	// diff2html envuelve el resultado en un documento; extraemos solo el cuerpo.
	const bodyMatch = htmlOutput.match(/<body>([\s\S]*?)<\/body>/);
	return bodyMatch ? bodyMatch[1] : htmlOutput;
}

// ---------------------------------------------------------------------------
// HTML generation
// ---------------------------------------------------------------------------

function writeIndex(reformas) {
	const parts = [
		'<!DOCTYPE html>\n<html lang="es">\n<head>\n',
		'<meta charset="utf-8">\n',
		'<meta name="viewport" content="width=device-width, initial-scale=1">\n',
		`<title>CPEUM — Índice de ${TITLE}</title>\n`,
		'<meta property="og:title" content="CPEUM — Índice de Decretos" />\n',
		'<meta property="og:description" content="Índice de las decretos constitucionales de la CPEUM desde 1917" />\n',
		'<meta property="og:type" content="website" />\n',
		'<meta property="og:url" content="https://cpeum.mx/decretos/" />\n',
		'<meta property="og:image" content="https://cpeum.mx/img/cpeum.png" />\n',
		'<meta name="twitter:card" content="summary" />\n',
		"<style>\n",
		GLOBAL_CSS,
		"</style>\n</head>\n<body>\n",
		BANNER,
		`<h1>Índice de ${TITLE}</h1>\n`,
	];

	for (const reforma of [...reformas].reverse()) {
		const first = reforma.commits[0];
		const fuente = first ? { subject: first.subject } : null;

		parts.push('<div class="reforma">\n');

		if (fuente) {
			parts.push(
				'<p class="reforma-titulo">',
				`<a href="${reforma.numero}.html">`,
				`${reforma.numero} 🔗.</a> ${htmlEscape(fuente.subject)}`,
			);
			const iso = reforma.publicacion;
			const datetimeAttr = iso ? ` datetime="${iso}"` : "";
			parts.push(
				` 📅 <time${datetimeAttr} class="reforma-fecha">${htmlEscape(iso || "")}</time></p>\n`,
			);
		} else {
			// Decretos sin commit: solo el número y el campo "decreto", sin vínculo.
			parts.push(`<p class="reforma-titulo">${reforma.numero}.</p>\n`);
		}

		// En los decretos sin commit solo se muestra el contenido del campo
		// "decreto" (sin vínculo).
		parts.push(
			`<p class="reforma-resumen">${linkifyDof(htmlEscape(reforma.decreto))}</p>\n`,
		);
		parts.push('<hr class="reforma-sep">\n');
		parts.push("</div>\n");
	}

	parts.push("</body>\n</html>\n");
	const filepath = path.join(OUTDIR, "index.html");
	fs.writeFileSync(filepath, parts.join(""), "utf-8");
	console.log(`  ${path.relative(process.cwd(), filepath)}`);
}

function writeReformaFile(reforma, prev, next) {
	const filename = `${reforma.numero}.html`;
	const parts = [];
	const first = reforma.commits[0];
	const title = `CPEUM — ${first.subject}`;
	const commitUrl = `${GITHUB_URL}/commit/${first.hash}`;

	parts.push(HTML_HEADER);
	parts.push(`<title>${htmlEscape(title)}</title>\n`);
	parts.push(
		`<meta property="og:title" content="${htmlEscape(first.subject)}" />\n`,
	);
	parts.push(
		'<meta property="og:description" content="',
		htmlEscape(`Decreto ${reforma.numero}: ${reforma.decreto || ""}`),
		'" />\n',
	);
	parts.push('<meta property="og:type" content="article" />\n');
	parts.push(
		`<meta property="og:url" content="https://cpeum.mx/decretos/${filename}" />\n`,
	);
	parts.push(
		'<meta property="og:image" content="https://cpeum.mx/img/cpeum.png" />\n',
	);
	parts.push(
		'<meta name="twitter:card" content="summary" />\n</head>\n<body>\n',
	);
	parts.push(BANNER);

	// Navegación cronológica: anterior / siguiente (solo decretos con commit).
	parts.push('<nav class="reforma-nav">\n');
	if (prev) {
		parts.push(
			'<span class="nav-prev"><a href="',
			`${prev.numero}.html">`,
			"← ",
			htmlEscape(prev.commits[0].subject),
			"</a></span>\n",
		);
	} else {
		parts.push('<span class="nav-prev nav-disabled">← Anterior</span>\n');
	}
	if (next) {
		parts.push(
			'<span class="nav-next"><a href="',
			`${next.numero}.html">`,
			htmlEscape(next.commits[0].subject),
			" →</a></span>\n",
		);
	} else {
		parts.push('<span class="nav-next nav-disabled">Siguiente →</span>\n');
	}
	parts.push("</nav>\n");

	parts.push(`<h1>${htmlEscape(first.subject)}</h1>\n`);
	parts.push(`<p class="reforma-numero">Decreto ${reforma.numero}</p>\n`);
	parts.push(
		'<p class="commit-meta">',
		`<a href="${commitUrl}" rel="external noreferrer" target="_blank">`,
		"Ver commit en GitHub",
		"</a> — ",
		htmlEscape(first.date),
		"</p>\n",
	);
	if (first.body) {
		parts.push(
			`<pre class="commit-body">${linkifyDof(htmlEscape(first.body))}</pre>\n`,
		);
	}

	for (const commit of reforma.commits) {
		const rstFiles = getRstFiles(commit.hash);
		const parent = `${commit.hash}~1`;

		for (const rstFile of rstFiles) {
			const diffHtml = buildDiff(parent, commit.hash, rstFile);
			if (diffHtml) {
				parts.push(diffHtml);
				parts.push("\n");
			} else {
				parts.push(`<p>Sin cambios en ${htmlEscape(rstFile)}.</p>\n`);
			}
		}
	}

	parts.push(FOOTER);
	const filepath = path.join(OUTDIR, filename);
	fs.writeFileSync(filepath, parts.join(""), "utf-8");
	console.log(`  ${path.relative(process.cwd(), filepath)}`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function generate() {
	fs.mkdirSync(OUTDIR, { recursive: true });
	const decretos = loadDecretos();
	const commits = getReformaCommits();
	const reformas = buildReformas(decretos, commits);
	const conCommit = reformas.filter((r) => r.commits.length > 0);
	const sinCommit = reformas.filter((r) => r.commits.length === 0);

	console.log(
		`${reformas.length} decretos (${conCommit.length} con commit, ${sinCommit.length} sin).`,
	);
	writeIndex(reformas);
	for (let i = 0; i < conCommit.length; i++) {
		writeReformaFile(conCommit[i], conCommit[i - 1], conCommit[i + 1]);
	}
	console.log(`\nGenerado en: ${OUTDIR}`);
}

try {
	generate();
} catch (error) {
	console.error("Error:", error.message);
	process.exit(1);
}
