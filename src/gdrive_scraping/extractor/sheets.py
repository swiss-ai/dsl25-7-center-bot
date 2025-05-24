def extract_text_from_sheets(service, file_id):
    request = service.files().export(fileId=file_id, mimeType='text/csv')
    return request.execute().decode('utf-8')