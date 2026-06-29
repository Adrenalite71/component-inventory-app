# Inventário de Componentes Eletrônicos

Uma aplicação desktop poderosa e intuitiva desenvolvida para organizar, gerenciar e pesquisar componentes eletrônicos (como Resistores PTH/SMD, Capacitores, Transistores, Circuitos Integrados e mais). O sistema permite o mapeamento físico preciso em gavetas e cálculo dinâmico de parâmetros.

## Funcionalidades

- **Busca Paramétrica Avançada:** Encontre componentes rapidamente filtrando por categoria, localização física, valores exatos ou propriedades específicas.
- **Sincronização em Rede Local (LAN):** Projetado para ambientes de trabalho reais. O sistema possui arquitetura embutida para operar em modo **Servidor (Host)** ou **Cliente**, permitindo que múltiplos computadores na mesma oficina compartilhem e atualizem o mesmo banco de dados em tempo real.
- **Calculadoras Integradas Bidirecionais:** Ferramentas nativas para decodificação rápida direto na bancada. Inclui calculadora bidirecional inteligente para Resistores PTH (Cores ↔ Valores) e decodificadores automáticos de códigos alfanuméricos para Resistores SMD e Capacitores SMD.
- **Subdivisões Dinâmicas de Gavetas:** Controle total sobre o seu armazenamento físico. Adicione, edite ou exclua gavetas com quantidades ilimitadas e flexíveis de subdivisões. O preenchimento automático sincroniza dados e cores nativamente ao editar.
- **Privacidade e Persistência de Dados:** Todo o inventário é salvo de forma segura (SQLite), operando de forma 100% offline no modo local ou centralizado com segurança na sua própria rede.

## Como Baixar e Usar

1. Acesse a aba **[Releases](../../releases)** localizada no lado direito desta página do GitHub.
2. Baixe o arquivo `.exe` da versão mais recente.
3. Este aplicativo é um executável **standalone (portátil)**. Não é necessária nenhuma instalação complexa — basta dar um duplo clique no arquivo baixado e começar a gerenciar seu inventário!

> [!WARNING]
> ### Aviso Importante - Windows SmartScreen
> 
> Como esta é uma ferramenta independente, de código aberto e construída sem um certificado digital pago, o **Windows Defender SmartScreen** poderá bloqueá-la em sua primeira execução, exibindo um aviso de "Aplicativo não reconhecido" ou "Inseguro".
> 
> Para utilizar o aplicativo com segurança, siga os seguintes passos:
> 1. Na tela azul do *Windows Protect*, clique no texto **"Mais informações"** (More info).
> 2. Em seguida, clique no botão **"Executar assim mesmo"** (Run anyway).
