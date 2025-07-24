from main import app
from flask import render_template, request, send_file, redirect, url_for, session
import re
import tempfile
import os
import fitz  #

# Habilita sessão para guardar dados temporários
app.secret_key = "segredo-muito-seguro"

padroes = {
    "CPF": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
    "CNPJ": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
    "Telefone": r"\b\(?\d{2}\)?\s?\d{4,5}-\d{4}\b",
    "E-mail": r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b",
    "Senha": r"\bsenha\s*[:=]?\s*\S+",
    "Processo CNJ": r"\b\d{7}-\d{2}\.\d{4}\.\d{1}\.\d{2}\.\d{4}\b",
    "CEP": r"\b\d{5}-\d{3}\b",
    "Cartão de Crédito": r"\b(?:\d[ -]*?){13,16}\b",
    "RG": r"\b\d{2}\.\d{3}\.\d{3}-\d{1}\b",
    "Passaporte": r"\b[A-Z]{1}\d{7}\b",
}


@app.route("/", methods=["GET", "POST"])
def homepage():
    if request.method == "POST":
        arquivo = request.files["arquivo"]
        conteudo = arquivo.read().decode("utf-8")

        ocorrencias = []
        for tipo, regex in padroes.items():
            for m in re.finditer(regex, conteudo):
                ocorrencias.append({
                    "tipo": tipo,
                    "texto": m.group(),
                    "start": m.start(),
                    "end": m.end(),
                    "id": f"{m.start()}_{m.end()}"  
                })

        # Armazenar dados na sessão
        session["conteudo"] = conteudo
        session["ocorrencias"] = ocorrencias

        return render_template("preview.html", conteudo=conteudo, ocorrencias=ocorrencias)

    return render_template("index.html")


@app.route("/aplicar", methods=["POST"])
def aplicar_tarjas():
    conteudo = session.get("conteudo", "")
    ocorrencias = session.get("ocorrencias", [])

    selecionados = request.form.getlist("selecionados")

    # Aplicar as tarjas manualmente com controle de deslocamento
    deslocamento = 0
    for item in ocorrencias:
        if f"{item['start']}_{item['end']}" in selecionados:
            inicio = item["start"] + deslocamento
            fim = item["end"] + deslocamento
            substituto = f"[TARJADO-{item['tipo']}]"
            conteudo = conteudo[:inicio] + substituto + conteudo[fim:]
            deslocamento += len(substituto) - (fim - inicio)

    # Criar arquivo temporário
    temp_file = tempfile.NamedTemporaryFile(delete=False, mode="w+", encoding="utf-8", suffix="_tarjado.txt")
    temp_file.write(conteudo)
    temp_file.close()

    return send_file(temp_file.name, as_attachment=True, download_name="arquivo_tarjado.txt")



@app.route("/upload_pdf", methods=["GET", "POST"])
def upload_pdf():
    if request.method == "POST":
        if "arquivo_pdf" not in request.files:
            return "Erro: arquivo não enviado na requisição", 400
        
        arquivo = request.files["arquivo_pdf"]

        if arquivo.filename == "":
            return "Erro: nome do arquivo vazio", 400
        
        file_bytes = arquivo.read()

        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            return f"Erro ao abrir PDF: {e}", 400
        
        texto_total = ""
        ocorrencias = []

        for page in doc:
            texto_pagina = page.get_text()
            texto_total += texto_pagina + "\n--- Página {} ---\n".format(page.number + 1)
            for tipo, regex in padroes.items():
                for m in re.finditer(regex, texto_pagina, re.IGNORECASE):
                    ocorrencias.append({
                        "page": page.number,
                        "tipo": tipo,
                        "texto": m.group(),
                        "start": m.start(),
                        "end": m.end(),
                        "id": f"{page.number}_{m.start()}_{m.end()}"
                    })
        session["pdf_bytes"] = file_bytes
        session["pdf_ocorrencias"] = ocorrencias
        session["pdf_texto"] = texto_total
        
        return redirect(url_for("preview_pdf"))

    return render_template("upload_pdf.html")


@app.route("/preview_pdf", methods=["GET"])
def preview_pdf():
    texto_pdf = session.get("pdf_texto", "")
    ocorrencias_pdf = session.get("pdf_ocorrencias", [])
    if not texto_pdf or not ocorrencias_pdf:
        return redirect(url_for("upload_pdf"))

    return render_template("preview_pdf.html", texto_pdf=texto_pdf, ocorrencias_pdf=ocorrencias_pdf)



@app.route("/aplicar_tarjas_pdf", methods=["POST"])
def aplicar_tarjas_pdf():
    pdf_bytes = session.get("pdf_bytes")
    ocorrencias = session.get("pdf_ocorrencias", [])

    if not pdf_bytes or not ocorrencias:
        return redirect(url_for("upload_pdf"))

    selecionados = request.form.getlist("selecionados")

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        return f"Erro ao abrir PDF na aplicação das tarjas: {e}"

    for item in ocorrencias:
        id_ocorrencia = item["id"]
        if id_ocorrencia in selecionados:
            page_num = item["page"]
            texto_encontrado = item["texto"]
            page = doc[page_num]
            areas = page.search_for(texto_encontrado)
            for area in areas:
                page.add_redact_annot(area, fill=(0, 0, 0))

    for page in doc:
        page.apply_redactions()

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix="_tarjado.pdf")
    doc.save(temp_file.name)
    doc.close()

    return send_file(temp_file.name, as_attachment=True, download_name="arquivo_tarjado.pdf")


