import os
import re
import requests
from urllib.parse import urlparse
import tempfile
from datetime import datetime

# These will need to be installed
import PyPDF2
try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    
try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

class DocumentHandler:
    def __init__(self, storage_dir="resources"):
        """Initialize document handler with storage directory"""
        self.storage_dir = storage_dir
        self.documents = {}  # Store document metadata and content
        
        # Create storage directory if it doesn't exist
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)
    
    async def add_resource(self, resource_path, description=None):
        """Add a new resource file or URL to the document store"""
        try:
            # Check if resource is a URL
            if resource_path.startswith(('http://', 'https://')):
                return await self.add_url(resource_path, description)
            
            # Handle local file
            if not os.path.exists(resource_path):
                return False, f"File not found: {resource_path}"
            
            file_ext = os.path.splitext(resource_path)[1].lower()
            
            # Process different file types
            if file_ext == '.pdf':
                return await self.add_pdf(resource_path, description)
            elif file_ext == '.txt':
                return await self.add_text_file(resource_path, description)
            elif file_ext == '.docx':
                return await self.add_docx(resource_path, description)
            else:
                return False, f"Unsupported file type: {file_ext}"
                
        except Exception as e:
            return False, f"Error processing resource: {str(e)}"
    
    async def add_pdf(self, file_path, description=None):
        """Extract text from PDF and add to documents"""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                text = ""
                for page_num in range(len(reader.pages)):
                    text += reader.pages[page_num].extract_text() + "\n"
            
            doc_id = self._generate_id(file_path)
            self.documents[doc_id] = {
                'type': 'pdf',
                'source': file_path,
                'description': description or os.path.basename(file_path),
                'content': text,
                'added': datetime.now()
            }
            return True, doc_id
        except Exception as e:
            return False, f"Error processing PDF: {str(e)}"
    
    async def add_text_file(self, file_path, description=None):
        """Add text file content to documents"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
            
            doc_id = self._generate_id(file_path)
            self.documents[doc_id] = {
                'type': 'txt',
                'source': file_path,
                'description': description or os.path.basename(file_path),
                'content': text,
                'added': datetime.now()
            }
            return True, doc_id
        except Exception as e:
            return False, f"Error processing text file: {str(e)}"
    
    async def add_docx(self, file_path, description=None):
        """Extract text from DOCX and add to documents"""
        if not DOCX_AVAILABLE:
            return False, "python-docx not installed. Install with: pip install python-docx"
            
        try:
            doc = docx.Document(file_path)
            text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
            
            doc_id = self._generate_id(file_path)
            self.documents[doc_id] = {
                'type': 'docx',
                'source': file_path,
                'description': description or os.path.basename(file_path),
                'content': text,
                'added': datetime.now()
            }
            return True, doc_id
        except Exception as e:
            return False, f"Error processing DOCX: {str(e)}"
    
    async def add_url(self, url, description=None):
        """Fetch content from URL and add to documents"""
        if not BS4_AVAILABLE:
            return False, "BeautifulSoup not installed. Install with: pip install beautifulsoup4"
            
        try:
            response = requests.get(url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract main content (remove scripts, styles, etc.)
            for script in soup(["script", "style", "meta", "noscript", "iframe"]):
                script.extract()
            
            text = soup.get_text(separator='\n')
            # Clean up the text
            lines = (line.strip() for line in text.splitlines())
            text = "\n".join(line for line in lines if line)
            
            doc_id = self._generate_id(url)
            self.documents[doc_id] = {
                'type': 'url',
                'source': url,
                'description': description or url,
                'content': text,
                'added': datetime.now()
            }
            return True, doc_id
        except Exception as e:
            return False, f"Error processing URL: {str(e)}"
    
    def get_resources(self):
        """Get list of all available resources"""
        return [{
            'id': doc_id,
            'type': doc['type'],
            'description': doc['description'],
            'source': doc['source'],
            'added': doc['added']
        } for doc_id, doc in self.documents.items()]
    
    def get_resource_content(self, doc_id):
        """Get the content of a specific resource"""
        if doc_id in self.documents:
            return self.documents[doc_id]['content']
        return None
    
    def remove_resource(self, doc_id):
        """Remove a resource from the document store"""
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False
    
    async def search_resources(self, query):
        """Search all resources for relevant content related to query"""
        results = []
        
        for doc_id, doc in self.documents.items():
            content = doc['content']
            # Find paragraphs that might contain the answer
            paragraphs = content.split('\n\n')
            
            matched_paragraphs = []
            for para in paragraphs:
                if query.lower() in para.lower():
                    matched_paragraphs.append(para)
            
            if matched_paragraphs:
                results.append({
                    'doc_id': doc_id,
                    'source': doc['source'],
                    'type': doc['type'],
                    'description': doc['description'],
                    'content': matched_paragraphs
                })
        
        return results
    
    def _generate_id(self, source):
        """Generate a unique ID for the document based on source"""
        filename = os.path.basename(source)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{filename.split('.')[0]}_{timestamp}"