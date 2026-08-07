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
const mustache = require("mustache");
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

/* Chrome del sitio compartido con scripts/rst2html5.py: datos
   (templates/site.json), plantillas Mustache (templates/*.mustache) y hojas
   de estilo css/*.css. Estas páginas se generan bajo html/decretos/, por lo
   que los enlaces del banner llevan prefijo "../". */
const REPO_ROOT = path.resolve(__dirname, "..");
const CSS_DIR = path.join(REPO_ROOT, "css");
const TEMPLATES_DIR = path.join(REPO_ROOT, "templates");

const SITE = JSON.parse(
	fs.readFileSync(path.join(TEMPLATES_DIR, "site.json"), "utf-8"),
);
const GITHUB_URL = SITE.github_url;

const SITIO_CSS = fs.readFileSync(path.join(CSS_DIR, "sitio.css"), "utf-8");
const DECRETOS_CSS = fs.readFileSync(
	path.join(CSS_DIR, "decretos.css"),
	"utf-8",
);
const GLOBAL_CSS = `${SITIO_CSS}\n${DECRETOS_CSS}`;

const BANNER_TEMPLATE = fs.readFileSync(
	path.join(TEMPLATES_DIR, "banner.mustache"),
	"utf-8",
);
const HEAD_META_TEMPLATE = fs.readFileSync(
	path.join(TEMPLATES_DIR, "head_meta.mustache"),
	"utf-8",
);

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

/* Escape Mustache compatible con chevron (el motor de scripts/rst2html5.py):
   escapa `& < > "`, que es lo que espera el estándar, pero NO `/` ni `'`
   (el paquete `mustache` npm escapa también `/` y `'`). Así ambas
   plantillas compartidas se renderizan de forma idéntica, incluidas las
   URLs. */
function sharedEscape(text) {
	return String(text).replace(/[&<>"]/g, (char) => {
		switch (char) {
			case "&":
				return "&amp;";
			case "<":
				return "&lt;";
			case ">":
				return "&gt;";
			default:
				return "&quot;";
		}
	});
}

const MUSTACHE_OPTS = { escape: sharedEscape };

/* Banner renderizado desde la plantilla compartida; enlaces relativos a
   html/decretos/. */
function renderBanner() {
	return mustache.render(
		BANNER_TEMPLATE,
		{
			...SITE,
			cpeum_href: "../index.html",
			decretos_href: "index.html",
			estadisticas_href: "../estadisticas.html",
			acerca_href: "../acercade.html",
		},
		undefined,
		MUSTACHE_OPTS,
	);
}

/* Metadatos <head> compartidos. Toma el contexto de cada página; los enlaces
   a iconos/humans.txt usan prefijo "../" (html/decretos/). */
function renderHeadMeta({ ogTitle, ogDescription, ogType, ogUrl, canonical }) {
	return mustache.render(
		HEAD_META_TEMPLATE,
		{
			...SITE,
			og_title: ogTitle,
			og_description: ogDescription,
			og_type: ogType,
			og_url: ogUrl,
			twitter_title: ogTitle,
			canonical,
			icon_base: "../",
		},
		undefined,
		MUSTACHE_OPTS,
	);
}
// Git helpers
// ---------------------------------------------------------------------------

function runGit(args) {
	return execSync(["git", "-C cpeum-decretos", ...args].join(" "), {
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
		renderHeadMeta({
			ogTitle: "CPEUM — Índice de Decretos",
			ogDescription:
				"Índice de las decretos constitucionales de la CPEUM desde 1917",
			ogType: "website",
			ogUrl: "https://cpeum.mx/decretos/",
			canonical: "https://cpeum.mx/decretos/",
		}),
		"<style>\n",
		GLOBAL_CSS,
		'</style>\n</head>\n<body class="decretos">\n',
		renderBanner(),
		`<h1>Índice de ${TITLE}</h1>\n`,
	];

	for (const reforma of [...reformas].reverse()) {
		const first = reforma.commits[0];
		const fuente = first ? { subject: first.subject } : null;

		parts.push('<div class="reforma">\n');

		if (fuente) {
			parts.push(
				'<p class="reforma-titulo">',
				`<a rel="bookmark" href="${reforma.numero}.html">`,
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
		renderHeadMeta({
			ogTitle: title,
			ogDescription: `Decreto ${reforma.numero}: ${reforma.decreto || ""}`,
			ogType: "article",
			ogUrl: `https://cpeum.mx/decretos/${filename}`,
			canonical: `https://cpeum.mx/decretos/${filename}`,
		}),
	);
	parts.push('</head>\n<body class="decretos">\n');
	parts.push(renderBanner());

	// Navegación cronológica: anterior / siguiente (solo decretos con commit).
	parts.push('<nav class="reforma-nav">\n');
	if (prev) {
		parts.push(
			'<span class="nav-prev"><a rel="prev" href="',
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
			'<span class="nav-next"><a rel="next" href="',
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

	// Modo "url": busca el número de decreto del commit dado y escribe en
	// stdout la URL de su página de diff (usada por el CI de BlueSky).
	const hashArg = process.argv.indexOf("--url");
	if (hashArg !== -1 && process.argv.length > hashArg + 1) {
		const target = process.argv[hashArg + 1];
		const commit = commits.find((c) => c.hash === target);
		if (!commit || commit.numero === undefined) {
			console.error(
				`Error: no se encontró un decreto para el commit ${target}.`,
			);
			process.exit(1);
		}
		console.log(`https://cpeum.mx/decretos/${commit.numero}.html`);
		return;
	}

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
