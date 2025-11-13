"""
Claude Service - Komunikace s Claude API
"""

import anthropic
from typing import Optional, Dict, Any, List
import pandas as pd


class ClaudeService:
    """Service pro komunikaci s Claude API"""
    
    def __init__(self, api_key: str):
        """
        Inicializace Claude service
        
        Args:
            api_key: Anthropic API klíč
        """
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is empty!")
        
        print(f"ClaudeService: Initializing with key length {len(api_key)}")
        self.client = anthropic.Anthropic(api_key=api_key)
        print("ClaudeService: Client initialized successfully")
        self.model = "claude-sonnet-4-20250514"
    
    def generate_python_code(self, prompt: str, max_tokens: int = 2000) -> str:
        """
        Generuje Python kód na základě promptu
        
        Args:
            prompt: Prompt pro Claude
            max_tokens: Maximální počet tokenů
            
        Returns:
            Vygenerovaný Python kód
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text
    
    def generate_analysis(
        self, 
        prompt: str, 
        dataframe: pd.DataFrame,
        max_tokens: int = 2000
    ) -> str:
        """
        Generuje AI analýzu dat
        
        Args:
            prompt: Prompt pro analýzu
            dataframe: DataFrame s daty
            max_tokens: Maximální počet tokenů
            
        Returns:
            Analýza v textové formě
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return message.content[0].text
    
    def chat_completion(
        self, 
        messages: List[Dict[str, str]], 
        max_tokens: int = 2000
    ) -> str:
        """
        Multi-turn konverzace s Claude
        
        Args:
            messages: Seznam zpráv (role + content)
            max_tokens: Maximální počet tokenů
            
        Returns:
            Odpověď od Claude
        """
        message = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=messages
        )
        
        return message.content[0].text
    
    def extract_python_code(self, text: str) -> Optional[str]:
        """
        Extrahuje Python kód z odpovědi Claude
        
        Args:
            text: Text obsahující Python kód
            
        Returns:
            Extrahovaný Python kód nebo None
        """
        import re
        
        # Hledej ```python ... ``` bloky
        pattern = r'```python\s*(.*?)\s*```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        # Fallback - hledej jen ``` ... ```
        pattern = r'```\s*(.*?)\s*```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        return None