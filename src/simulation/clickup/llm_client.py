"""
LLM API Client
Handles API calls to various LLM providers for ticket insights generation
"""

import os
import time
import json
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from config import (
    LLM_PROVIDER, LLM_API_KEY, LLM_MODELS, 
    MAX_TOKENS_INPUT, MAX_TOKENS_OUTPUT
)


class LLMClient:
    """Enterprise-grade LLM API client for ticket insights"""
    
    PROVIDERS = {
        "openai": {
            "content_extractor": lambda r, is_new_api: r.output_text if is_new_api else r.choices[0].message.content,
            "usage_extractor": lambda u, is_new_api: {
                "prompt_tokens": getattr(u, "prompt_tokens", 0) if is_new_api else u.prompt_tokens,
                "completion_tokens": getattr(u, "completion_tokens", 0) if is_new_api else u.completion_tokens,
                "total_tokens": getattr(u, "total_tokens", 0) if is_new_api else u.total_tokens
            },
            "finish_reason_extractor": lambda r, is_new_api: "stop" if is_new_api else r.choices[0].finish_reason
        },
        "anthropic": {
            "content_extractor": lambda r: r.content[0].text,
            "usage_extractor": lambda u: {
                "prompt_tokens": u.input_tokens,
                "completion_tokens": u.output_tokens,
                "total_tokens": u.input_tokens + u.output_tokens
            },
            "finish_reason_extractor": lambda r: r.stop_reason
        },
        "google": {
            "content_extractor": lambda r: r.text,
            "usage_extractor": lambda u: {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "finish_reason_extractor": lambda r: "stop"
        }
    }
    
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
    
    def _get_provider_config(self):
        return self.PROVIDERS.get(self.client_type, {})
    
    def _get_model_prefix(self):
        for prefix in ["gpt-4", "o1", "o3"]:
            if self.model.startswith(prefix):
                return prefix
        return "default"
    
    def _is_new_api(self):
        return self.client_type == 'openai' and self._get_model_prefix() != "default"
    
    def count_tokens(self, text: str) -> int:
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
        try:
            is_new_api = self._is_new_api()
            
            if is_new_api:
                response = self.client.responses.create(
                    model=self.model,
                    input=messages,
                    temperature=temperature,
                    max_output_tokens=max_tokens
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            
            config = self._get_provider_config()
            usage = response.usage or {}
            
            return {
                'success': True,
                'content': config["content_extractor"](response, is_new_api),
                'model': response.model,
                'usage': config["usage_extractor"](usage, is_new_api),
                'finish_reason': config["finish_reason_extractor"](response, is_new_api)
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
            
            config = self._get_provider_config()
            
            return {
                'success': True,
                'content': config["content_extractor"](response),
                'model': response.model,
                'usage': config["usage_extractor"](response.usage),
                'finish_reason': config["finish_reason_extractor"](response)
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
            
            config = self._get_provider_config()
            
            return {
                'success': True,
                'content': config["content_extractor"](response),
                'model': self.model,
                'usage': config["usage_extractor"](None),
                'finish_reason': config["finish_reason_extractor"](response)
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
                    time.sleep(wait_time)
                    continue
                
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        
        return {
            'success': False,
            'error': f'Failed after {self.max_retries} attempts. Last error: {last_error}',
            'attempts': self.max_retries
        }
    
    def parse_response(self, response: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
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
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = MAX_TOKENS_OUTPUT
    ) -> Dict[str, Any]:
        if self.client_type == 'openai':
            return self.call_openai(messages, temperature, max_tokens)
        elif self.client_type == 'anthropic':
            return self.call_anthropic(messages, temperature, max_tokens)
        elif self.client_type == 'google':
            return self.call_google(messages, temperature, max_tokens)
        else:
            return {'success': False, 'error': 'Unknown client type'}
