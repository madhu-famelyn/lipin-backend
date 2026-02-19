import json
import re
class File_to_Base64:
    async def file_to_base64(self, file):
        from fastapi import HTTPException
        import base64
        content = await file.read()
        if len(content) > 800 * 1024:
            raise HTTPException(400, f"File too large: {file.filename}")
        
        # Reset file position for potential reuse
        await file.seek(0)
    
        return {
        "base64": base64.b64encode(content).decode('utf-8'),
        "filename": file.filename,
        "mime_type": file.content_type,
        "size_bytes": len(content)
            }
    def increment(self, amount=1):
        self.count += amount
        print(f"Count is now: {self.count}")

class Clean_JSON:
    def __init__(self, raw_response):
        self.raw_response = raw_response

    def clean_json_response(self):
        """Clean and extract JSON from AI response"""
        if not self.raw_response:
            return '{}'

        response = self.raw_response.strip()

        # Remove markdown code blocks - handle various formats
        # Remove ```json ... ``` blocks
        response = re.sub(r'```json\s*\n?', '', response)
        response = re.sub(r'```\s*$', '', response)
        response = re.sub(r'^```\s*', '', response, flags=re.MULTILINE)
        response = re.sub(r'\s*```$', '', response, flags=re.MULTILINE)

        # Remove any leading/trailing whitespace
        response = response.strip()

        # Find JSON content between first { and last }
        start = response.find('{')
        end = response.rfind('}')

        if start != -1 and end != -1 and end > start:
            response = response[start:end+1]
        elif response.startswith('['):
            # Handle JSON arrays
            end = response.rfind(']')
            if end != -1:
                response = response[:end+1]
        else:
            # No valid JSON found
            print(f"Warning: No valid JSON structure found in response: {response[:100]}...")
            return '{}'

        # Try parsing the JSON
        try:
            parsed = json.loads(response)
            return json.dumps(parsed)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Attempting to fix response...")

            # Try various fixes
            fixed_response = response

            # Fix unescaped newlines within strings
            fixed_response = fixed_response.replace('\r\n', '\\n').replace('\r', '\\n')

            # Fix single quotes to double quotes (common AI mistake)
            # Only do this outside of string values - simple approach
            try:
                parsed = json.loads(fixed_response)
                return json.dumps(parsed)
            except json.JSONDecodeError:
                pass

            # Try replacing newlines with spaces
            fixed_response = response.replace('\n', ' ').replace('\r', ' ')
            try:
                parsed = json.loads(fixed_response)
                return json.dumps(parsed)
            except json.JSONDecodeError:
                pass

            # Last resort - return empty object
            print(f"Failed to parse JSON. Raw response: {response[:200]}...")
            return '{}'

class Image_Processor:
    def __init__(self, base64_img ):
        self.base64_img = base64_img
    def convert_img_to_str(self):
        import base64
        from io import BytesIO
        from PIL import Image
        import pytesseract

        # Decode the base64 string
        img_data = base64.b64decode(self.base64_img.split(",")[1])
        
        # Convert bytes data to a PIL Image
        image = Image.open(BytesIO(img_data))

        text = pytesseract.image_to_string(image)

        return text

class Simple_File_Handler:
    """Simplified file processing for attachments"""
    
    @staticmethod
    def get_file_summary(file, file_size):
        """Simple file summary without complex content extraction"""
        try:
            content_type = getattr(file, 'content_type', None) or "unknown"
            filename = getattr(file, 'filename', 'unknown') or "unknown"
            
            # Simple file type detection
            if filename.lower().endswith('.pdf'):
                file_type = "PDF Document"
            elif filename.lower().endswith(('.docx', '.doc')):
                file_type = "Word Document"
            elif filename.lower().endswith(('.txt', '.md')):
                file_type = "Text Document"
            elif filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                file_type = "Image"
            else:
                file_type = "File"
            
            # Simple size formatting
            if file_size > 1024 * 1024:
                size_str = f"{file_size / (1024*1024):.1f}MB"
            else:
                size_str = f"{file_size / 1024:.1f}KB"
            
            return f"{file_type}: {filename} ({size_str}). Consider this attachment for context in post generation."
            
        except Exception as e:
            return f"Attachment: {getattr(file, 'filename', 'unknown file')}. Use for context in post generation."
    
    @staticmethod
    def should_use_base64(file_size):
        """Simple check if file should be base64 encoded"""
        # Limit to 2MB for base64 to avoid issues
        return file_size <= (2 * 1024 * 1024)