def extract_text_from_txt(service, file_id):
    request = service.files().get_media(fileId=file_id)
    return request.execute().decode('utf-8')