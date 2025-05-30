from googleapiclient.discovery import build

def extract_text_from_slides(service, file_id):
    slides_service = build('slides', 'v1', credentials=service._http.credentials)
    presentation = slides_service.presentations().get(presentationId=file_id).execute()

    text = ""
    for slide in presentation.get('slides', []):
        for element in slide.get('pageElements', []):
            shape = element.get('shape')
            if shape and 'text' in shape:
                text_elements = shape['text'].get('textElements', [])
                for te in text_elements:
                    if 'textRun' in te:
                        text += te['textRun'].get('content', '')
    return text