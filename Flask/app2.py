from flask import Flask, request, send_file, render_template_string
import fitz  # PyMuPDF
import io
import re

app = Flask(__name__)

# Padrões que podem ser tarjados
PADROES_SENSIVEIS = {
    "CPF": r'\b\d{3}\.\d{3}\.\d{3}-\d{2}\b',
    "RG": r'\b\d{1,2}\.?\d{3}\.?\d{3}-?\d{1}\b',
    "EMAIL": r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b',
    "TELEFONE": r'\(?\d{2}\)?\s?\d{4,5}-\d{4}',
    "CEP": r'\b\d{5}-\d{3}\b',
    "CNPJ": r'\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b',
    "CARTAO": r'(?:\d[ -]*?){13,16}',
    "PLACA": r'\b[A-Z]{3}-?\d{1}[A-Z0-9]{1}\d{2}\b',
    "DATA": r'\b\d{2}/\d{2}/\d{4}\b'
}

# HTML com checkboxes para seleção
HTML_FORM = """
<!doctype html>
<title>Tarjar PDF com Segurança</title>
<h2>Envie um PDF e escolha o que deseja ocultar com tarja segura:</h2>
<form method="post" enctype="multipart/form-data">
  <input type="file" name="pdffile" accept=".pdf" required><br><br>
  {% for chave in padroes %}
    <label><input type="checkbox" name="itens" value="{{ chave }}" checked> {{ chave }}</label><br>
  {% endfor %}
  <br>
  <button type="submit">Enviar e Tarjar</button>
</form>
"""

# Função principal com redactions reais
def aplicar_tarjas_em_pdf(doc, padroes):
    for pagina in doc:
        texto = pagina.get_text("text")
        for nome, regex in padroes.items():
            for match in re.finditer(regex, texto):
                termo = match.group()
                areas = pagina.search_for(termo)
                for area in areas:
                    # Marca para redigir com preenchimento preto
                    pagina.add_redact_annot(area, fill=(0, 0, 0))
        # Aplica redactions: remove texto original e coloca tarja
        pagina.apply_redactions()
    return doc

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        arquivo = request.files['pdffile']
        selecionados = request.form.getlist("itens")

        if not arquivo or not arquivo.filename.endswith('.pdf'):
            return "Arquivo inválido. Envie um .pdf.", 400

        padroes_ativos = {k: v for k, v in PADROES_SENSIVEIS.items() if k in selecionados}

        # Abre PDF da memória
        pdf_bytes = arquivo.read()
        doc = fitz.open("pdf", pdf_bytes)

        # Aplica tarjas reais
        aplicar_tarjas_em_pdf(doc, padroes_ativos)

        # Salva novo PDF na memória
        mem_file = io.BytesIO()
        doc.save(mem_file)
        mem_file.seek(0)
        doc.close()

        return send_file(
            mem_file,
            as_attachment=True,
            download_name="documento_tarjado.pdf",
            mimetype="application/pdf"
        )

    return render_template_string(HTML_FORM, padroes=PADROES_SENSIVEIS.keys())

if __name__ == '__main__':
    app.run(debug=True)
