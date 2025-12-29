class LLMClient:
    """Enterprise-grade LLM API client for ticket insights"""
    
"""
Enterprise-Grade LLM API Client
Handles API calls to various LLM providers for ticket insights generation
"""

import os
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import requests

from config import (
    LLM_PROVIDER, LLM_API_KEY, LLM_MODELS, 
    MAX_TOKENS_INPUT, MAX_TOKENS_OUTPUT
)


class LLMClient:
    """Enterprise-grade LLM API client for ticket insights"""
    
    def __init__(
        self, 
        provider: str = LLM_PROVIDER,
        api_key: str = LLM_API_KEY,
        model: Optional[str] = None,
        max_retries: int = 3,
        timeout: int = 60
    ):
        self.provider = provider.lower()
        self.api_key = api_key or os.getenv('LLM_API_KEY')
        self.model = model or LLM_MODELS.get(self.provider)
        self.max_retries = max_retries
        self.timeout = timeout
        
        if not self.api_key:
            raise ValueError(f"API key not provided for {self.provider}")
        
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize provider-specific client"""
        if self.provider == 'openai':
            try:
                import openai
                self.client = openai.OpenAI(api_key=self.api_key)
                self.client_type = 'openai'
            except ImportError:
                raise ImportError("openai package not installed. Run: pip install openai")
        
        elif self.provider == 'anthropic':
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                self.client_type = 'anthropic'
            except ImportError:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
        
        elif self.provider == 'google':
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.client = genai.GenerativeModel(self.model)
                self.client_type = 'google'
            except ImportError:
                raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")
        
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def count_tokens(self, text: str) -> int:
        """Estimate token count for text"""
        if self.provider == 'openai':
            try:
                import tiktoken
                encoding = tiktoken.encoding_for_model(self.model)
                return len(encoding.encode(text))
            except:
                return len(text) // 4
        else:
            return len(text) // 4
    
    def call_openai(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_OUTPUT
    ) -> Dict[str, Any]:
        """Call OpenAI API"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            return {
                'success': True,
                'content': response.choices[0].message.content,
                'model': response.model,
                'usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                },
                'finish_reason': response.choices[0].finish_reason
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def call_anthropic(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_OUTPUT
    ) -> Dict[str, Any]:
        """Call Anthropic Claude API"""
        try:
            system_message = None
            user_messages = []
            
            for msg in messages:
                if msg['role'] == 'system':
                    system_message = msg['content']
                else:
                    user_messages.append(msg)
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_message,
                messages=user_messages
            )
            
            return {
                'success': True,
                'content': response.content[0].text,
                'model': response.model,
                'usage': {
                    'prompt_tokens': response.usage.input_tokens,
                    'completion_tokens': response.usage.output_tokens,
                    'total_tokens': response.usage.input_tokens + response.usage.output_tokens
                },
                'finish_reason': response.stop_reason
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def call_google(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_OUTPUT
    ) -> Dict[str, Any]:
        """Call Google Gemini API"""
        try:
            prompt_parts = []
            for msg in messages:
                role = "User" if msg['role'] == 'user' else "Assistant"
                prompt_parts.append(f"{role}: {msg['content']}")
            
            prompt = "\n\n".join(prompt_parts)
            
            response = self.client.generate_content(
                prompt,
                generation_config={
                    'temperature': temperature,
                    'max_output_tokens': max_tokens
                }
            )
            
            return {
                'success': True,
                'content': response.text,
                'model': self.model,
                'usage': {
                    'prompt_tokens': 0,
                    'completion_tokens': 0,
                    'total_tokens': 0
                },
                'finish_reason': 'stop'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'error_type': type(e).__name__
            }
    
    def call_llm(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_OUTPUT
    ) -> Dict[str, Any]:
        """Universal LLM call method"""
        messages = []
        
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        
        messages.append({'role': 'user', 'content': prompt})
        
        if self.client_type == 'openai':
            return self.call_openai(messages, temperature, max_tokens)
        elif self.client_type == 'anthropic':
            return self.call_anthropic(messages, temperature, max_tokens)
        elif self.client_type == 'google':
            return self.call_google(messages, temperature, max_tokens)
        else:
            return {
                'success': False,
                'error': f'Unknown client type: {self.client_type}'
            }
    
    def call_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_OUTPUT
    ) -> Dict[str, Any]:
        """Call LLM with retry logic and exponential backoff"""
        last_error = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.call_llm(prompt, system_prompt, temperature, max_tokens)
                
                if response['success']:
                    return response
                
                last_error = response.get('error', 'Unknown error')
                error_type = response.get('error_type', '')
                
                if 'rate_limit' in error_type.lower() or 'rate limit' in str(last_error).lower():
                    wait_time = (2 ** attempt) + (attempt * 0.5)
                    print(f"Rate limit hit. Waiting {wait_time:.1f}s before retry {attempt}/{self.max_retries}")
                    time.sleep(wait_time)
                    continue
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    print(f"Attempt {attempt} failed: {last_error}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    print(f"Exception on attempt {attempt}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
        
        return {
            'success': False,
            'error': f'Failed after {self.max_retries} attempts. Last error: {last_error}',
            'attempts': self.max_retries
        }
    
    def parse_response(self, response: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """Parse and validate LLM response"""
        if not response.get('success'):
            return False, response.get('error', 'Unknown error'), {}
        
        content = response.get('content', '').strip()
        
        if not content:
            return False, 'Empty response from LLM', {}
        
        metadata = {
            'model': response.get('model'),
            'usage': response.get('usage', {}),
            'finish_reason': response.get('finish_reason'),
            'timestamp': datetime.now().isoformat()
        }
        
        return True, content, metadata
    
    def extract_json_from_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response (handles markdown code blocks)"""
        content = content.strip()
        
        if content.startswith('```json'):
            content = content[7:]
        elif content.startswith('```'):
            content = content[3:]
        
        if content.endswith('```'):
            content = content[:-3]
        
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                start = content.find('{')
                end = content.rfind('}') + 1
                if start != -1 and end > start:
                    return json.loads(content[start:end])
            except:
                pass
        
        return None
    
    def generate_insights(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        parse_json: bool = False
    ) -> Dict[str, Any]:
        """Generate insights from tickets with full error handling"""
        
        if not system_prompt:
            system_prompt = """You are an expert project management AI assistant. 
Analyze ticket data and provide clear, actionable insights.
Focus on identifying bottlenecks, risks, and opportunities for improvement.
Be concise and specific in your recommendations."""
        
        response = self.call_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature
        )
        
        success, content, metadata = self.parse_response(response)
        
        result = {
            'success': success,
            'timestamp': datetime.now().isoformat(),
            'provider': self.provider,
            'model': self.model
        }
        
        if success:
            result['insights'] = content
            result['metadata'] = metadata
            
            if parse_json:
                json_data = self.extract_json_from_response(content)
                if json_data:
                    result['structured_insights'] = json_data
        else:
            result['error'] = content
        
        return result
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_OUTPUT
    ) -> Dict[str, Any]:
        """Multi-turn conversation support"""
        
        if self.client_type == 'openai':
            response = self.call_openai(messages, temperature, max_tokens)
        elif self.client_type == 'anthropic':
            response = self.call_anthropic(messages, temperature, max_tokens)
        elif self.client_type == 'google':
            response = self.call_google(messages, temperature, max_tokens)
        else:
            return {'success': False, 'error': 'Unknown client type'}
        
        return response
    
    def validate_prompt_length(self, prompt: str, max_tokens: int = MAX_TOKENS_INPUT) -> Tuple[bool, int]:
        """Validate prompt doesn't exceed token limit"""
        token_count = self.count_tokens(prompt)
        
        if token_count > max_tokens:
            return False, token_count
        
        return True, token_count
    
    def truncate_prompt(self, prompt: str, max_tokens: int = MAX_TOKENS_INPUT) -> str:
        """Truncate prompt to fit within token limit"""
        current_tokens = self.count_tokens(prompt)
        
        if current_tokens <= max_tokens:
            return prompt
        
        ratio = max_tokens / current_tokens
        target_length = int(len(prompt) * ratio * 0.95)
        
        truncated = prompt[:target_length]
        
        last_newline = truncated.rfind('\n')
        if last_newline > target_length * 0.8:
            truncated = truncated[:last_newline]
        
        truncated += "\n\n[Note: Content truncated to fit token limit]"
        
        return truncated
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get API usage statistics"""
        return {
            'provider': self.provider,
            'model': self.model,
            'max_retries': self.max_retries,
            'timeout': self.timeout
        }
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test LLM API connection"""
        try:
            response = self.call_llm(
                prompt="Respond with 'OK' if you can read this.",
                system_prompt="You are a helpful assistant.",
                temperature=0.0,
                max_tokens=10
            )
            
            if response['success']:
                return True, f"Connection successful. Model: {response.get('model')}"
            else:
                return False, f"Connection failed: {response.get('error')}"
        
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"


if __name__ == "__main__":
    print("\n" + "="*70)
    print("LLM CLIENT - CONNECTION TEST")
    print("="*70)
    
    try:
        client = LLMClient()
        
        print(f"\nProvider: {client.provider}")
        print(f"Model: {client.model}")
        
        print("\n[1] Testing connection...")
        success, message = client.test_connection()
        if success:
            print(f"  ✓ {message}")
        else:
            print(f"  ✗ {message}")
        
        if success:
            print("\n[2] Testing simple prompt...")
            response = client.call_with_retry(
                prompt="List 3 key metrics for tracking software project health.",
                system_prompt="You are a project management expert.",
                temperature=0.7
            )
            
            if response['success']:
                print(f"  ✓ Response received")
                print(f"  Tokens used: {response['usage']['total_tokens']}")
                print(f"\n  Response preview:")
                print(f"  {response['content'][:200]}...")
            else:
                print(f"  ✗ Error: {response.get('error')}")
        
        print("\n" + "="*70)
    
    except Exception as e:
        print(f"\n✗ Error initializing LLM client: {e}")
        print("\nMake sure you have:")
        print("1. Set LLM_API_KEY in .env file")
        print("2. Installed required package:")
        print("   - For OpenAI: pip install openai")
        print("   - For Anthropic: pip install anthropic")
        print("   - For Google: pip install google-generativeai")
