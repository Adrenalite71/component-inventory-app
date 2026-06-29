import json
import os

class ReleaseNotesModal(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Novidades da Versão")
        self.geometry("600x450")
        self.grab_set()

        lbl_title = ctk.CTkLabel(self, text="O que há de novo?", font=ctk.CTkFont(size=24, weight="bold"))
        lbl_title.pack(pady=(20, 10))

        textbox = ctk.CTkTextbox(self, wrap="word", font=ctk.CTkFont(size=14))
        textbox.pack(expand=True, fill="both", padx=20, pady=(0, 20))
        
        changelog = """
## v1.0.5
* Correção de carregamento de dados nas gavetas (edição de componentes agora preenche os dados corretamente).
* Sincronização corrigida na tela de pesquisa paramétrica.
* Adicionado painel de novidades e registro de versão.

## v1.0.4
* Adicionadas ferramentas de Calculadora Eletrônica (Resistor PTH, Resistor SMD, Capacitor SMD).
* Adicionado ajuste rápido de estoque (+ / -) direto na aba de Pesquisa via duplo-clique.

## v1.0.3
* Calculadora de códigos de cores para resistores PTH e exibição formatada.
* Correções no gerenciamento de gavetas e salvamento de componentes.
"""
        textbox.insert("0.0", changelog.strip())
        textbox.configure(state="disabled")
        
        btn_close = ctk.CTkButton(self, text="Fechar", command=self.destroy)
        btn_close.pack(pady=(0, 20))
