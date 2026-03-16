import json
from ollama import Client
import os
from models import Playbook, GeneratorOutput, DeltaOperation, DeltaOperationAction

# Dedicated Ollama client routed to the background local server
client = Client(host='https://rugose-sportively-janella.ngrok-free.dev')
MODEL_NAME = 'llama3:latest' 

class Generator:
    def generate(self, chat_history: list, playbook: Playbook, context: str) -> GeneratorOutput:
        rules = "\n".join([f"- {b.rule}" for b in playbook.bullets])
        
        # Build conversational history string
        # Increased to 10 messages so the model can remember earlier context properly
        history_str = ""
        for msg in chat_history[-10:]: 
            history_str += f"{msg['role'].capitalize()}: {msg['content']}\n"
            
        prompt = f"""
        You are a strictly compliant college assistant. 

        *** ABSOLUTE HIGHEST PRIORITY: ADMIN PLAYBOOK RULES ***
        You MUST obey these custom rules. Check these rules BEFORE generating any response. If they conflict with default instructions, these rules ALWAYS OVERRIDE them:
        {rules}
        *******************************************************

        CRITICAL BEHAVIORS:
        1. If the user asks for personal/private information (like "What is my GPA?" or "What is my major?"), but you DO NOT see [Private Data Auth Success] in the Context below, you MUST reply asking for their secret password/key.
        2. If the user provides a secret key, use the [Private Data Auth Success] context to answer their personal questions securely. DO NOT leak information from the student database unless the user has specifically provided that secret key.
        3. If the user states a new fact about themselves (e.g. "My name is Nitesh", "I love pizza"), you must reply EXACTLY with the following sentence: "Are you sure? I will remember: <the fact they said>".
        4. When answering questions about User Facts (like "what is my name"), look at the [Learned Facts] array in the context. Synthesize the facts naturally instead of just repeating the raw fact string.
        5. Answer general questions based on the Context retrieved. Do not hallucinate.
        
        Context retrieved from DB (includes general info and private info if authenticated):
        {context}
        
        Recent Conversation History:
        {history_str}
        
        Output ONLY valid JSON with strictly two fields: 'response' (string) and 'sources' (list of strings). Do not output markdown blocks outside the JSON.
        """
        try:
            # Enforce JSON mode natively in the Ollama client
            response = client.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}], format='json')
            content = response['message']['content']
            
            # Since format='json' is used, we generally don't need markdown stripping, but keep as fallback
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            return GeneratorOutput(**data)
        except Exception as e:
            print(f"Error in Generator: {e}")
            return GeneratorOutput(response=f"An error occurred while generating a response. Details: {str(e)}", sources=[])

class Reflector:
    def evaluate(self, student_feedback: str) -> str:
        if student_feedback == "invalid":
            return "harmful"
        return "safe"

class Curator:
    def draft_fix(self, query: str, response: str) -> DeltaOperation:
        prompt = f"""
        The following chatbot interaction was flagged as invalid or harmful.
        User Query: {query}
        Bot Response: {response}
        
        Draft a new prompt rule to prevent this mistake in the future.
        Output ONLY valid JSON for a DeltaOperation:
        {{
            "action": "ADD",
            "target_id": null,
            "new_rule": "The new rule text..."
        }}
        """
        try:
            res = client.chat(model=MODEL_NAME, messages=[{'role': 'user', 'content': prompt}])
            content = res['message']['content']
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
                
            data = json.loads(content)
            return DeltaOperation(**data)
        except Exception as e:
            return DeltaOperation(action=DeltaOperationAction.ADD, target_id=None, new_rule="Fallback: Avoid inaccurate responses.")