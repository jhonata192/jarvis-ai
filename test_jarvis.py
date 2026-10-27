import sys
import unittest
from jarvis.core.agent import JarvisAssistant
from jarvis.tools.system_tools import SystemTools

def test_jarvis():
    print("--- Testando Inicialização do Jarvis ---")
    agent = JarvisAssistant()
    
    print("\n1. Testando Ferramentas de Sistema...")
    status = agent.tools.get_system_status()
    print(f"Status obtido com sucesso: {status}")
    assert "cpu_percent" in status

    print("\n2. Testando RAG (Indexação e Consulta de Aprendizados)...")
    doc_id = agent.learn("teste_modulo", "O Jarvis foi configurado com sucesso e opera com AGY e RAG.")
    print(f"Resultado do aprendizado: {doc_id}")
    
    queries = agent.rag.query("Como o Jarvis foi configurado?", n_results=1)
    print(f"Memória recuperada: {queries}")
    assert len(queries) > 0

    print("\n3. Testando Comunicação Jarvis + AGY Provider...")
    resposta = agent.ask("Quem é você e quais capacidades você acabou de verificar no RAG?")
    print(f"\nResposta do Jarvis:\n{resposta}\n")
    assert len(resposta) > 0

    print("\n[OK] Todos os testes essenciais do Jarvis passaram com sucesso!")

if __name__ == "__main__":
    test_jarvis()
