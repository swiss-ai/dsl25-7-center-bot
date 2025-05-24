def extract_text_from_docs(service, file_id):
    request = service.files().export(fileId=file_id, mimeType='text/plain')
    return request.execute().decode('utf-8')