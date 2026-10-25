set -e
CSS=/tmp/pdf.css
cat > $CSS <<'CSSEOF'
@page { size: A4; margin: 20mm 18mm; }
body { font-family: "DejaVu Serif", Georgia, serif; font-size: 10.5pt; line-height: 1.45; color: #111; }
h1 { font-size: 19pt; line-height: 1.2; margin: 0 0 0.4em 0; }
h2 { font-size: 14pt; margin: 1.4em 0 0.4em 0; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
h3 { font-size: 11.5pt; margin: 1.1em 0 0.3em 0; }
h4 { font-size: 10.5pt; margin: 0.9em 0 0.2em 0; }
p { margin: 0 0 0.6em 0; text-align: justify; }
code, pre { font-family: "DejaVu Sans Mono", monospace; font-size: 8.8pt; }
pre { background: #f6f6f6; border: 1px solid #e0e0e0; padding: 6px 8px; white-space: pre-wrap; word-wrap: break-word; }
table { border-collapse: collapse; width: 100%; font-size: 9.2pt; margin: 0.5em 0 0.9em 0; }
th, td { border: 1px solid #ccc; padding: 3px 6px; text-align: left; vertical-align: top; }
th { background: #f0f0f0; }
blockquote { border-left: 3px solid #ccc; margin: 0.5em 0; padding: 0.2em 0 0.2em 10px; color: #333; }
hr { border: 0; border-top: 1px solid #ddd; margin: 1.2em 0; }
img { max-width: 100%; }
CSSEOF
for f in "$@"; do
  base="${f%.md}"
  pandoc "$f" -f gfm -t html5 -s --metadata title="" -c "$CSS" -o "/tmp/$(basename $base).html"
  wkhtmltopdf --quiet --page-size A4 --enable-local-file-access \
    --margin-top 16mm --margin-bottom 16mm --margin-left 15mm --margin-right 15mm \
    --footer-font-size 7 --footer-right "[page]/[topage]" \
    "/tmp/$(basename $base).html" "$base.pdf"
  echo "built $base.pdf"
done
