#!/usr/bin/env python3
"""Merge raw question banks into questions.json and generate a standalone index.html study app."""
import json, os, re, random

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "raw")
LETTERS = ["A", "B", "C", "D"]


def remap_letters(text, remap):
    """Remap standalone option-letter references (A/B/C/D) in explanation prose.
    Only matches a single capital A-D not glued to other alphanumerics, so words
    like APAC, MCP, SQL, DROP, CTA are left untouched."""
    return re.sub(r"(?<![A-Za-z0-9])([ABCD])(?![A-Za-z0-9])",
                  lambda m: remap[m.group(1)], text)


def spread_answers(questions, seed=7):
    """Reorder questions so no two consecutive items share the same answer letter
    (greedy: always take the letter with the most remaining that differs from the
    previous one). With a balanced bank this is always achievable."""
    rnd = random.Random(seed)
    buckets = {l: [] for l in LETTERS}
    for q in questions:
        buckets[q["answer"]].append(q)
    for l in LETTERS:
        rnd.shuffle(buckets[l])
    result, last = [], None
    for _ in range(len(questions)):
        cand = [l for l in LETTERS if buckets[l] and l != last]
        if not cand:
            cand = [l for l in LETTERS if buckets[l]]
        mx = max(len(buckets[l]) for l in cand)
        l = rnd.choice([c for c in cand if len(buckets[c]) == mx])
        result.append(buckets[l].pop())
        last = l
    return result


def balance_answers(questions, seed=42):
    """Permute each question's options so the correct answer is evenly spread
    across A/B/C/D, remapping any letter references inside the explanation."""
    rnd = random.Random(seed)
    targets = (LETTERS * ((len(questions) // 4) + 1))[:len(questions)]
    rnd.shuffle(targets)
    for q, target in zip(questions, targets):
        old_ans = q["answer"]
        opts = q["options"]
        correct_text = opts[old_ans]
        others = [opts[l] for l in LETTERS if l != old_ans]
        rnd.shuffle(others)
        new_opts = {target: correct_text}
        for l, txt in zip([l for l in LETTERS if l != target], others):
            new_opts[l] = txt
        text_to_new = {v: k for k, v in new_opts.items()}
        remap = {l: text_to_new[opts[l]] for l in LETTERS}
        q["explanation"] = remap_letters(q["explanation"], remap)
        q["options"] = {l: new_opts[l] for l in LETTERS}  # keep A-D key order
        q["answer"] = target

META = {
    "title": "Claude Certified Architect — Foundations",
    "passMark": 720,
    "scaleMin": 100,
    "scaleMax": 1000,
    "domains": {
        "D1": {"name": "Agentic Architecture & Orchestration", "tag": "D1 · AGENTIC",     "weight": 0.27, "color": "#7c5cff"},
        "D2": {"name": "Tool Design & MCP Integration",        "tag": "D2 · TOOLS/MCP",   "weight": 0.18, "color": "#5b8def"},
        "D3": {"name": "Claude Code Configuration & Workflows","tag": "D3 · CLAUDE CODE",  "weight": 0.20, "color": "#3fb37f"},
        "D4": {"name": "Prompt Engineering & Structured Output","tag": "D4 · PROMPTING",   "weight": 0.20, "color": "#e0823d"},
        "D5": {"name": "Context Management & Reliability",     "tag": "D5 · CONTEXT",     "weight": 0.15, "color": "#9aa0aa"},
    },
}

# Aulas por domínio (conteúdo didático mostrado antes da sessão de perguntas).
# Conteúdo autoral/confiável — pode conter <b> para destacar termos.
LESSONS = {
    "D1": {
        "intro": "Como decidir entre um único prompt, um agente ou vários agentes — e como orquestrar passos de forma confiável, segura e barata.",
        "sections": [
            {"h": "Quando usar agentes (e quando não)", "points": [
                "Tarefa simples e bem-definida → um único prompt ou uma chamada. Agentes só se justificam quando há decisões dinâmicas, uso de ferramentas e passos imprevisíveis.",
                "Multi-agente (orquestrador + subagentes) compensa em tarefas amplas, abertas e paralelizáveis (ex.: pesquisa em muitas fontes). Para algo trivial e de alto volume, a orquestração só adiciona custo e latência."]},
            {"h": "Padrões de orquestração", "points": [
                "<b>Prompt chaining</b>: a saída validada de um passo alimenta o próximo (gerar → revisar → refinar). Bom quando cada etapa é verificável.",
                "<b>Routing</b>: classifica a entrada e despacha para um handler especializado.",
                "<b>Orchestrator-worker</b>: um líder distribui subtarefas a workers e agrega os resultados.",
                "<b>Evaluator-optimizer</b>: um gera, outro avalia e devolve crítica acionável, em loop — sempre com limite de iterações."]},
            {"h": "Paralelismo e barreiras", "points": [
                "Chamadas independentes devem rodar em paralelo; um passo que depende de várias só começa após uma <b>barreira</b> que espera todas.",
                "Não serialize trabalho independente (aumenta latência à toa) nem inicie um passo antes de suas dependências existirem.",
                "Controle a concorrência (pool/semáforo) ao chamar APIs com rate limit — fan-out ilimitado causa falhas em cascata.",
                "Se um único passo domina a latência (caminho crítico), <b>divida-o</b> em sub-tarefas paralelas (map-reduce) e combine — encurtar o passo lento ajuda mais que mexer no resto."]},
            {"h": "Confiabilidade e segurança", "points": [
                "Passos críticos e irreversíveis (pagamento, exclusão, ordem de risco) devem ser garantidos por <b>código determinístico</b>, não pela obediência do modelo a um prompt.",
                "<b>Least privilege</b>: cada (sub)agente recebe só as ferramentas que a tarefa exige.",
                "Erros devem ser estruturados (tipo, se é retryable, contexto) para o agente se recuperar sozinho; defina um <b>fallback</b> explícito em vez de deixar o líder inventar um resultado.",
                "Subagentes devem retornar um <b>resultado destilado</b>, não o rascunho/contexto bruto — senão estouram o contexto do líder.",
                "Passos com efeito colateral devem ser <b>idempotentes</b> (ou com checkpoint), para que um retry após falha não duplique efeitos nem refaça tudo do zero."]},
            {"h": "Humano no loop", "points": [
                "Coloque o checkpoint de aprovação <b>imediatamente antes</b> da ação irreversível, não depois."]},
        ],
        "worked": [
            {"q": "Um classificador de moderação decide se um conteúdo viola a política. Em casos ambíguos o modelo às vezes erra, e um falso negativo aqui é caro. A equipe quer aumentar a confiabilidade da decisão sem trocar de modelo. Qual abordagem é a mais adequada?",
             "options": {
                "A": "Rodar a classificação várias vezes em paralelo e decidir por voto majoritário (self-consistency).",
                "B": "Aumentar a temperatura para o modelo explorar mais interpretações antes de decidir.",
                "C": "Pedir no prompt para o modelo ter certeza e só responder quando estiver confiante.",
                "D": "Encaminhar todo conteúdo a revisão humana antes de qualquer decisão automática."},
             "answer": "A",
             "breakdown": {
                "A": "<b>Certa.</b> Rodar N amostras independentes e agregar por maioria é o padrão de <b>parallelization/voting</b> para elevar a confiabilidade sem trocar o modelo — um erro isolado é diluído pelos demais votos.",
                "B": "<b>Errada.</b> Temperatura maior <b>aumenta a variância</b>, ou seja, deixa a decisão menos confiável, não mais.",
                "C": "<b>Errada.</b> A confiança autodeclarada pelo modelo não é calibrada; pedir para ele ter certeza não cria nenhuma garantia de acerto.",
                "D": "<b>Errada (runner-up).</b> Mandar tudo para humano elimina a automação e não escala no volume; o voto majoritário já eleva a confiabilidade, deixando o humano só para os casos em que os votos empatam."}},
            {"q": "Um agente autônomo opera num ambiente com ferramentas perigosas (deploy, exclusão). A auditoria exige que ele só consiga executar ações de um conjunto pré-aprovado, mesmo que o modelo decida fazer algo fora disso. Qual arquitetura atende melhor?",
             "options": {
                "A": "Listar de forma enfática no system prompt as ações permitidas e proibir o resto.",
                "B": "Separar um planner (o modelo propõe um plano) de um executor determinístico que só roda ações da allow-list e recusa qualquer outra.",
                "C": "Adicionar um subagente revisor que checa cada ação proposta antes de executá-la.",
                "D": "Baixar a temperatura e fixar a versão do modelo para o comportamento ficar previsível."},
             "answer": "B",
             "breakdown": {
                "A": "<b>Errada.</b> System prompt é orientação, não fronteira de segurança; prompt injection ou um erro do modelo o contorna.",
                "B": "<b>Certa.</b> Confinar a execução a uma allow-list aplicada por <b>código</b> (executor determinístico) torna qualquer ação fora do conjunto <b>estruturalmente impossível</b>, independentemente do que o modelo decida.",
                "C": "<b>Errada (runner-up).</b> Um revisor ajuda como defesa em profundidade, mas ainda é um modelo verificando outro (probabilístico) e adiciona latência; não certifica zero ações proibidas como o gate determinístico.",
                "D": "<b>Errada.</b> Determinismo de amostragem (temperatura/versão) não restringe <b>quais</b> ações são possíveis."}},
            {"q": "Um fluxo tem 3 passos: extrair entidades de um documento, validar essas entidades contra um cadastro, e gerar um resumo que usa só as entidades validadas. Para reduzir latência, um engenheiro quer rodar os três em paralelo. Qual avaliação é correta?",
             "options": {
                "A": "Rodar os três em paralelo e o passo de resumo tenta de novo até os outros terminarem.",
                "B": "Paralelizar é correto porque os três operam sobre o mesmo documento.",
                "C": "Os passos têm dependência de dados (cada um usa a saída do anterior), então devem ser encadeados (sequenciais); paralelizar daria resultado incorreto.",
                "D": "Paralelizar os dois primeiros e depois rodar o resumo."},
             "answer": "C",
             "breakdown": {
                "A": "<b>Errada.</b> Iniciar o resumo antes de suas entradas existirem e ficar tentando desperdiça chamadas e arrisca agir sobre dados incompletos.",
                "B": "<b>Errada.</b> Compartilhar a mesma origem (o documento) não torna os passos independentes; há dependência explícita de saída→entrada.",
                "C": "<b>Certa.</b> É um caso de <b>prompt chaining</b>: validar precisa das entidades extraídas e o resumo precisa das validadas. Aqui o lever é <b>correção</b>, não latência — paralelizar quebra a corrente.",
                "D": "<b>Errada (runner-up).</b> Não dá nem para paralelizar os dois primeiros: validar depende de extrair. Não existe par independente para sobrepor."}},
        ],
    },
    "D2": {
        "intro": "MCP padroniza como expor capacidades a modelos. O segredo está em modelar tools/resources/prompts corretamente e desenhar ferramentas seguras e fáceis de o modelo usar certo.",
        "sections": [
            {"h": "MCP em uma frase", "points": [
                "MCP é um <b>padrão aberto</b> para expor <b>tools</b>, <b>resources</b> e <b>prompts</b> a modelos, de forma interoperável entre hosts. Não tem a ver com pesos do modelo nem com compressão/cache.",
                "Um servidor MCP pode ser <b>local</b> (transporte <b>stdio</b>) ou <b>remoto</b> (transporte <b>HTTP</b>) — o transporte não muda o que são tools/resources/prompts."]},
            {"h": "Tools vs Resources vs Prompts", "points": [
                "<b>Tool</b>: ação com efeito colateral que o modelo invoca (ex.: transferir dinheiro).",
                "<b>Resource</b>: contexto somente-leitura que o host injeta (ex.: saldo, histórico).",
                "<b>Prompt</b>: template reutilizável/parametrizado de interação, para padronizar e compartilhar."]},
            {"h": "Descrição e parâmetros", "points": [
                "A <b>descrição</b> da tool é o principal sinal de seleção — diga exatamente o que ela faz e <b>quando</b> usá-la. Ferramentas redundantes confundem; consolide.",
                "Restrinja entradas com <b>schema</b> e <b>enums</b> em vez de string livre, para reduzir chamadas inválidas."]},
            {"h": "Erros e idempotência", "points": [
                "Retorne <b>erros estruturados</b> (tipo, campo problemático, se é retryable) — nunca um stack trace cru nem um 200 OK silencioso sobre algo que falhou.",
                "Para ações com efeito colateral que podem ser repetidas (retry após timeout), use uma <b>idempotency key</b> para o servidor não duplicar o efeito.",
                "Prefira tools <b>stateless</b>: cada chamada carrega tudo que precisa, sem depender de estado de sessão escondido."]},
            {"h": "Segurança e blast radius", "points": [
                "Evite a tool faz-tudo (ex.: rodar qualquer operação no banco) — divida em ferramentas estreitas e remova capacidades destrutivas do alcance do agente.",
                "Para ações destrutivas/irreversíveis, exija um <b>confirmation gate</b> humano."]},
            {"h": "Saída para o modelo, não para humanos", "points": [
                "Se o consumidor é o modelo, retorne dados <b>estruturados/tipados</b> (não Markdown com emoji).",
                "Pagine/filtre no servidor para não inundar o contexto com milhares de linhas."]},
        ],
        "worked": [
            {"q": "Você expõe a um agente: (1) ler a documentação interna da empresa e (2) abrir um chamado no service desk. Pela convenção MCP, como modelar cada um?",
             "options": {
                "A": "Documentação como resource (contexto somente-leitura) e abrir chamado como tool (ação com efeito colateral).",
                "B": "Ambos como tools, já que o agente invoca os dois pelo nome.",
                "C": "Ambos como resources, pois pertencem ao mesmo sistema interno.",
                "D": "Documentação como tool (para o modelo recarregar quando quiser) e o chamado como resource."},
             "answer": "A",
             "breakdown": {
                "A": "<b>Certa.</b> MCP separa por <b>efeito</b>: leitura de contexto = resource; ação com efeito colateral = tool. Ler a doc é leitura; abrir chamado muda o estado do mundo.",
                "B": "<b>Errada.</b> Nem tudo que se invoca pelo nome é tool; tratar a leitura como tool perde a distinção de segurança entre <b>ler</b> e <b>agir</b>.",
                "C": "<b>Errada.</b> Abrir chamado cria um registro (efeito colateral) — não é somente-leitura.",
                "D": "<b>Errada (runner-up).</b> Inverte a semântica: faz a ação (chamado) parecer contexto passivo e a leitura parecer ação, escondendo o risco real."}},
            {"q": "Uma tool list_events retorna todos os eventos de um ano (dezenas de milhares), mas o agente só precisa dos da última semana para responder. Os passos seguintes ficaram caros e pouco confiáveis. Qual é a melhor correção?",
             "options": {
                "A": "Manter o retorno completo e instruir o agente a ignorar o que não interessa.",
                "B": "Deixar o modelo resumir a lista enorme antes de usá-la.",
                "C": "Adicionar parâmetros de filtro/intervalo e paginação na tool para o servidor retornar só os eventos relevantes.",
                "D": "Aumentar a janela de contexto para caber o ano inteiro."},
             "answer": "C",
             "breakdown": {
                "A": "<b>Errada.</b> Mandar ignorar não impede que milhares de itens entrem no contexto, consumindo tokens e diluindo a atenção.",
                "B": "<b>Errada (runner-up).</b> Resumir <b>depois</b> ainda traz tudo ao contexto (custo) e pode perder dados; melhor não trazer o irrelevante.",
                "C": "<b>Certa.</b> Filtrar e paginar <b>no servidor</b> faz a tool devolver só o necessário — corta custo, respeita a janela e foca a atenção. O lever é controlar o volume na fonte.",
                "D": "<b>Errada.</b> A janela é fixa e cara; aumentá-la (quando dá) não corrige a diluição de atenção sobre dados irrelevantes."}},
        ],
    },
    "D3": {
        "intro": "Como configurar o Claude Code de forma confiável e compartilhável: o que é determinístico (hooks/permissões) vs orientação (CLAUDE.md), e o que é pessoal vs do time.",
        "sections": [
            {"h": "CLAUDE.md — contexto auto-carregado", "points": [
                "<b>Projeto</b> (.claude/CLAUDE.md, commitado): convenções do time, aplicadas a todos.",
                "<b>Pessoal</b> (~/.claude/CLAUDE.md): suas preferências em todos os projetos, sem impor ao time.",
                "Nunca coloque <b>segredos</b> (tokens) no CLAUDE.md — ele é commitado e injetado no contexto.",
                "<b>.claude/rules/</b>: convenções aplicadas <b>só aos caminhos</b> que batem com o glob do frontmatter (ex.: src/api/**) — automático e sem inchar o contexto sempre-ligado."]},
            {"h": "Configurações e permissões", "points": [
                "<b>settings.json</b> (commitado): regras do time. <b>settings.local.json</b> (git-ignored): pessoal, não vai pro repo.",
                "Precedência de permissão: <b>deny &gt; ask &gt; allow</b>. Use deny rules como camada de segurança.",
                "<b>Negar</b> uma permissão é recusar <b>aquela</b> ação — ajuste o curso (faça diferente), não re-tente o mesmo comando; uma aprovação não é permanente."]},
            {"h": "Hooks — execução determinística do harness", "points": [
                "<b>PreToolUse</b>: roda <b>antes</b> e pode <b>bloquear</b> a ação (ex.: barrar git push --force ou rm -rf).",
                "<b>PostToolUse</b>: roda <b>depois</b> que a ação ocorreu (ex.: rodar um formatador) — não previne execução.",
                "Hooks são executados pelo harness, então valem quando você precisa de garantia, não de orientação."]},
            {"h": "Skills vs Slash commands", "points": [
                "<b>Skill</b>: capacidade empacotada (instruções + scripts + recursos) que o modelo carrega <b>autonomamente</b> quando relevante.",
                "<b>Slash command</b>: atalho <b>invocado explicitamente</b> pelo usuário; nunca carrega sozinho.",
                "Comandos do time ficam em <b>.claude/commands/</b> (commitado no projeto); os pessoais em <b>~/.claude/commands/</b>."]},
            {"h": "Subagentes, plan mode e MCP", "points": [
                "Despache buscas grandes/ruidosas a um <b>subagente</b> para isolar o contexto da sessão principal.",
                "<b>Plan mode</b>: para refactors grandes multi-arquivo, o Claude propõe um plano para aprovação antes de editar.",
                "Compartilhe servidores MCP do time via <b>.mcp.json</b> commitado na raiz do projeto."]},
            {"h": "Headless / CI", "points": [
                "Use <b>claude -p</b> (print) para execução não-interativa; <b>--output-format json</b> para saída estruturada que outro script consome."]},
        ],
        "worked": [
            {"q": "Você quer (a) pré-aprovar pessoalmente alguns comandos sem afetar o time e (b) compartilhar com todos a regra que bloqueia rm -rf. Onde cada um deve ficar?",
             "options": {
                "A": "O pessoal em settings.local.json (git-ignored) e a regra do time em settings.json (commitado).",
                "B": "Ambos em settings.json, para todo mundo ter a mesma configuração.",
                "C": "Ambos em settings.local.json, para não poluir o repositório.",
                "D": "O pessoal no CLAUDE.md e a regra do time em settings.json."},
             "answer": "A",
             "breakdown": {
                "A": "<b>Certa.</b> settings.local.json é pessoal e não commitado (ideal para a allow-list só sua); settings.json é commitado e vale para o time (ideal para a deny rule compartilhada).",
                "B": "<b>Errada.</b> Commitar sua allow-list pessoal a impõe a todos — o oposto de não afetar o time.",
                "C": "<b>Errada.</b> Se a regra do time ficar só no local (git-ignored), ela não chega aos colegas.",
                "D": "<b>Errada (runner-up).</b> CLAUDE.md é contexto/orientação auto-carregada, não o mecanismo de permissão; regra de permissão fica em settings, não em prosa."}},
            {"q": "Requisito: nenhum comando que escreva no diretório /prod pode chegar a executar (tem de ser barrado antes); e, depois de cada edição de arquivo .py, rodar o formatador. Qual combinação de hooks está correta?",
             "options": {
                "A": "PreToolUse para barrar a escrita em /prod (antes) e PostToolUse para formatar o .py (depois).",
                "B": "PostToolUse para os dois.",
                "C": "PreToolUse para os dois.",
                "D": "PostToolUse para barrar (pegando logo após) e PreToolUse para formatar antes."},
             "answer": "A",
             "breakdown": {
                "A": "<b>Certa.</b> Só o <b>PreToolUse</b> roda antes e pode <b>negar</b> a ação — é o único momento de barrar a escrita em /prod. Formatar reage a algo que já aconteceu (arquivo escrito), então é <b>PostToolUse</b>.",
                "B": "<b>Errada.</b> PostToolUse dispara após a execução; não consegue impedir a escrita em /prod.",
                "C": "<b>Errada.</b> Formatar em PreToolUse não faz sentido — o arquivo ainda não foi escrito; é reação pós-edição.",
                "D": "<b>Errada (runner-up).</b> Está invertido: não se barra depois (já executou) nem se formata antes (ainda não há conteúdo)."}},
        ],
    },
    "D4": {
        "intro": "Como obter o comportamento e o formato certos do modelo — e por que estrutura confiável vem de mecanismos fora do modelo, não de pedir por favor no prompt.",
        "sections": [
            {"h": "Instruções claras", "points": [
                "Seja direto e específico; prefira instruções <b>positivas</b> (o que fazer) às negativas (dizer não faça X costuma falhar).",
                "Defina o <b>papel/persona</b> (system role) para ancorar vocabulário e elevar a precisão em domínios especializados.",
                "<b>Posição importa</b>: o modelo dá mais atenção ao início e ao fim do prompt; uma regra crítica perdida no meio (lost-in-the-middle) deve ir para perto do fim e ser ancorada num exemplo."]},
            {"h": "Garantir formato de saída", "points": [
                "Pedir retorne só JSON no texto <b>não garante</b> nada. Para um consumidor que rejeita payload inválido, use <b>forced tool use</b> + <b>JSON schema</b> e <b>valide-e-tente-de-novo</b> na camada da tool.",
                "<b>Prefill</b> da resposta (ex.: começar com a chave de abertura) trava o início do formato e corta preâmbulo.",
                "<b>temperature 0</b> reduz variância, mas <b>não</b> impõe estrutura nem correção.",
                "Para campos que podem faltar, defina um <b>contrato de ausência</b> explícito: a chave <b>sempre presente</b> com valor <b>null</b> (não 'N/A', vazio, nem omitir a chave)."]},
            {"h": "Few-shot e decomposição", "points": [
                "<b>Few-shot</b> fixa tom, formato e fronteiras de decisão (ex.: o caso ambíguo entre duas categorias).",
                "Um prompt pedindo 5 coisas ao mesmo tempo costuma falhar — <b>decomponha</b> em passos focados."]},
            {"h": "Raciocínio (chain-of-thought)", "points": [
                "CoT ajuda em decisões multi-fator/complexas: faça o modelo raciocinar passo a passo antes do veredito.",
                "Mas CoT <b>não é sempre bom</b>: numa classificação binária simples de alto volume, ele só adiciona latência e custo sem ganho."]},
            {"h": "Dados não-confiáveis e alucinação", "points": [
                "Separe instruções de dados com <b>delimitadores XML/seções</b> e marque conteúdo externo (ex.: e-mail do cliente) como <b>não-confiável</b>, para resistir a prompt injection.",
                "Para reduzir alucinação em respostas sobre documentos, exija <b>grounding</b>: citar/quotar o trecho que sustenta cada afirmação."]},
        ],
        "worked": [
            {"q": "Um serviço a jusante rejeita qualquer payload que não seja JSON válido segundo um schema fixo. O prompt já diz para responder só com JSON, mas ~3% das respostas vêm com texto extra e quebram a integração. Qual mudança é a mais confiável?",
             "options": {
                "A": "Reforçar a instrução, escrevendo em maiúsculas que qualquer texto fora do JSON é erro, no topo e no fim do prompt.",
                "B": "Definir a extração como tool com JSON schema, forçar a chamada e validar na camada da tool, repetindo em caso de falha.",
                "C": "Adicionar exemplos few-shot mostrando só o JSON puro.",
                "D": "Definir temperature 0 para o modelo seguir a instrução de forma determinística."},
             "answer": "B",
             "breakdown": {
                "A": "<b>Errada.</b> É a mesma instrução em prosa que já existe, só mais alta; não garante estrutura e o 3% mostra que reforçar texto já estagnou.",
                "B": "<b>Certa.</b> Forçar tool com schema e <b>validar+repetir</b> torna o contrato de tipo <b>aplicável</b>: payload inválido é barrado e refeito antes de chegar ao consumidor.",
                "C": "<b>Errada (runner-up).</b> Few-shot eleva a aderência, mas a saída continua texto livre <b>não validado</b> — pode seguir escapando malformada.",
                "D": "<b>Errada.</b> temperature 0 reduz variância, não impõe schema; pode até fixar deterministicamente um formato errado."}},
            {"q": "Um classificador binário (spam / não-spam) roda a milhões de mensagens por dia, com orçamento de latência apertado, e já está com boa acurácia. Um colega sugere adicionar chain-of-thought só para garantir. Qual é a melhor avaliação?",
             "options": {
                "A": "Não adicionar CoT: a tarefa é simples e de altíssimo volume; o raciocínio extra só acrescenta latência e custo sem ganho relevante de acurácia.",
                "B": "Adicionar CoT, porque CoT sempre melhora a qualidade.",
                "C": "Adicionar CoT e compensar a latência subindo a temperatura.",
                "D": "Trocar por uma tool forçada com enum de duas opções para garantir o formato."},
             "answer": "A",
             "breakdown": {
                "A": "<b>Certa.</b> CoT ajuda em decisões multi-fator/complexas; numa classificação binária simples, de alto volume e latência crítica, ele só adiciona tokens, custo e atraso sem ganho — então o certo é <b>não</b> usar.",
                "B": "<b>Errada.</b> Premissa falsa: CoT não melhora sempre; em tarefas simples é desperdício.",
                "C": "<b>Errada.</b> Temperatura não reduz latência (e ainda piora a consistência); não faz sentido como compensação.",
                "D": "<b>Errada (runner-up).</b> Forçar enum garante o <b>formato</b>, mas o formato não é o problema aqui; não endereça o trade-off de adicionar raciocínio numa tarefa que não precisa."}},
        ],
    },
    "D5": {
        "intro": "O contexto é finito e caro. Esta área cobre como caber, reusar e proteger o contexto, além de confiabilidade sob carga.",
        "sections": [
            {"h": "Janela de contexto e recuperação", "points": [
                "A janela é <b>fixa</b> — não dá para aumentar na hora. Para corpora grandes, use <b>RAG</b>: recupere só os trechos relevantes em vez de concatenar tudo.",
                "<b>Menos é mais</b>: encher de documentos marginalmente relevantes dilui a atenção e piora a resposta (context rot). Curadoria &gt; volume.",
                "<b>Context pollution</b>: dados ruidosos de um passo não devem vazar para os próximos; isole e passe só o necessário."]},
            {"h": "Compaction", "points": [
                "Perto do limite, o harness <b>compacta</b>: resume o contexto antigo e segue com o resumo + o contexto recente. Não reinicia nem descarta silenciosamente o mais novo.",
                "Decisões críticas devem ser persistidas em <b>estado externo durável</b> (arquivo/DB) para sobreviver à compaction."]},
            {"h": "Prompt caching", "points": [
                "Reusa o <b>prefixo processado</b> do prompt (não respostas finais). Coloque o conteúdo <b>estável primeiro</b> e o variável por último.",
                "O TTL é <b>curto</b> (~minutos) e não permanente; tráfego esporádico deixa o cache expirar. Um bloco que muda no topo (timestamp/id) invalida tudo.",
                "Não exige temperature 0."]},
            {"h": "Message Batches API (processamento em lote)", "points": [
                "<b>O que é</b>: processamento <b>assíncrono</b> em lote — você envia muitas requisições de uma vez e busca os resultados depois (não é em tempo real; você consulta o status até concluir).",
                "<b>Vantagem</b>: ~<b>50% mais barato</b> (input e output) que chamadas síncronas.",
                "<b>Prazo</b>: cada lote conclui em <b>até ~24h</b> (muitas vezes bem antes), mas <b>sem</b> SLA de baixa latência.",
                "<b>Correlação</b>: cada requisição leva um <b>custom_id</b>; os resultados podem voltar fora de ordem e você casa cada um pelo custom_id.",
                "<b>Use quando</b>: jobs offline/noturnos, classificação ou avaliação em massa — nada esperando resposta na hora.",
                "<b>NÃO use quando</b>: precisa de resposta interativa ou tem SLA apertado (ex.: autocomplete, dashboard a cada 5 min) — aí vão chamadas síncronas/paralelas, mesmo custando mais."]},
            {"h": "Latência: streaming", "points": [
                "<b>Streaming</b> melhora a <b>latência percebida</b> (time-to-first-token) em respostas longas e interativas — o oposto do caso de batch."]},
            {"h": "Confiabilidade sob carga", "points": [
                "Para 429/529, use <b>retry com backoff exponencial + jitter</b> — não um loop apertado de retries idênticos."]},
        ],
        "worked": [
            {"q": "Um painel interno precisa reclassificar 5.000 itens a cada 5 minutos e exibir o resultado quase em tempo real. Para economizar, sugeriram usar a Message Batches API (~50% mais barata). Qual avaliação é correta?",
             "options": {
                "A": "Usar a Batches API: o desconto compensa e 5.000 itens cabem bem num lote.",
                "B": "A Batches API não serve: é assíncrona e sem SLA de baixa latência (até ~24h), incompatível com o ciclo de 5 min; aqui vão chamadas síncronas/paralelas, mesmo custando mais.",
                "C": "Usar a Batches API e consultar o status a cada poucos segundos para ter resultado quase imediato.",
                "D": "Concatenar os 5.000 itens num único prompt e classificar tudo de uma vez."},
             "answer": "B",
             "breakdown": {
                "A": "<b>Errada.</b> O desconto não importa se o resultado pode demorar horas; quem decide é o <b>SLA de 5 min</b>.",
                "B": "<b>Certa.</b> O lever é a <b>tolerância de latência</b>. Batches é ótimo para jobs offline (barato, até ~24h, correlaciona por custom_id), mas <b>sem</b> SLA de baixa latência — não atende um ciclo de 5 min. Logo, síncrono/paralelo.",
                "C": "<b>Errada (runner-up).</b> Fazer polling frequente não acelera o lote; não há garantia de conclusão em minutos, então o painel pode ficar desatualizado.",
                "D": "<b>Errada.</b> Um prompt gigante com 5.000 itens estoura/dilui o contexto e degrada a acurácia; não é assim que se faz classificação em massa."}},
            {"q": "Cada requisição tem um system prompt estável de 15k tokens e termina com a pergunta do usuário. Para ajudar na depuração, alguém colocou um id único de requisição no topo do prompt. O cache quase nunca acerta. Qual é a causa e a correção?",
             "options": {
                "A": "O id único no topo muda o prefixo a cada chamada e invalida o cache; a correção é tirar o id do topo, mantendo o conteúdo estável primeiro e o variável no fim.",
                "B": "O cache exige temperature 0; basta zerar a temperatura.",
                "C": "O cache guarda respostas finais; como a pergunta muda, nunca casa.",
                "D": "O system prompt é grande demais para ser cacheável; basta encurtá-lo."},
             "answer": "A",
             "breakdown": {
                "A": "<b>Certa.</b> Caching reusa o <b>prefixo processado</b>; qualquer coisa que mude no início (um id por requisição) quebra o prefixo e zera o acerto. Põe-se o estável primeiro e o volátil por último.",
                "B": "<b>Errada.</b> Caching não tem exigência de temperature 0; zerar não resolve.",
                "C": "<b>Errada.</b> Caching não armazena respostas finais — reusa o prefixo do prompt; perguntas diferentes ainda aproveitam o prefixo estável.",
                "D": "<b>Errada (runner-up).</b> Um prefixo grande e <b>estável</b> é justamente o cenário ideal de cache; o vilão é o id mutável no topo, não o tamanho."}},
        ],
    },
}

# order: new domain banks first, then the earlier v1 set
FILES = ["d1.json", "d2.json", "d3.json", "d4.json", "d5.json", "v1.json",
         "hard_d1.json", "hard_d2.json", "hard_d3.json", "hard_d4.json", "hard_d5.json",
         "hard2_d1.json", "hard2_d2.json", "hard2_d3.json", "hard2_d4.json", "hard2_d5.json"]

questions = []
for fn in FILES:
    with open(os.path.join(RAW, fn), encoding="utf-8") as f:
        arr = json.load(f)
    src = fn.replace(".json", "")
    for obj in arr:
        obj["src"] = src
        obj.setdefault("difficulty", "normal")  # files without the field are Foundations/normal
        questions.append(obj)

for i, q in enumerate(questions, 1):
    q["id"] = i

# balance letters + spread consecutive WITHIN each difficulty tier, so each tier is
# independently fair (Hard-only and Normal-only both stay balanced and non-repetitive)
groups = []
for diff in ("normal", "hard"):
    g = [q for q in questions if q["difficulty"] == diff]
    balance_answers(g)
    g = spread_answers(g)
    groups.append(g)
questions = groups[0] + groups[1]

# sanity: every answer key exists in options, domain known
for q in questions:
    assert q["answer"] in q["options"], f"bad answer in q{q['id']}"
    assert q["domain"] in META["domains"], f"bad domain in q{q['id']}"

payload = {"meta": META, "questions": questions, "lessons": LESSONS}

with open(os.path.join(ROOT, "questions.json"), "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

# counts per domain
counts = {}
for q in questions:
    counts[q["domain"]] = counts.get(q["domain"], 0) + 1
print("Total questions:", len(questions))
print("Per domain:", counts)
diffc = {}
for q in questions:
    diffc[q["difficulty"]] = diffc.get(q["difficulty"], 0) + 1
print("Per difficulty:", diffc)
for diff in ("normal", "hard"):
    adist = {}
    for q in questions:
        if q["difficulty"] == diff:
            adist[q["answer"]] = adist.get(q["answer"], 0) + 1
    print(f"Answer distribution [{diff}]:", {k: adist.get(k, 0) for k in LETTERS})

HTML = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Claude Architect · Exam Trainer</title>
<style>
:root{
  --bg:#0a0a0b; --panel:#141416; --panel2:#1b1b1f; --line:#2a2a30;
  --txt:#ededf0; --mut:#8b8b94; --acc:#e0823d; --ok:#3fb37f; --bad:#e0574b;
  --d1:#7c5cff; --d2:#5b8def; --d3:#3fb37f; --d4:#e0823d; --d5:#9aa0aa;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--bg);color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;letter-spacing:.06em}
.wrap{max-width:920px;margin:0 auto;padding:24px 20px 80px}
header.top{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:14px 20px;position:sticky;top:0;background:rgba(10,10,11,.92);backdrop-filter:blur(8px);z-index:5}
.brand{display:flex;align-items:center;gap:14px}
.brand b{font-weight:800}
.brand .sub{color:var(--mut);font-size:12px}
.btn{cursor:pointer;border:1px solid var(--line);background:var(--panel2);color:var(--txt);border-radius:999px;padding:9px 16px;font-size:13px;transition:.15s}
.btn:hover{border-color:#3a3a44}
.btn.primary{background:#fff;color:#000;border-color:#fff;font-weight:700}
.btn.primary:hover{opacity:.9}
.btn.ghost{background:transparent}
.btn:disabled{opacity:.4;cursor:not-allowed}
h1{font-size:22px;margin:6px 0 2px}
.lead{color:var(--mut);font-size:14px;margin:0 0 22px}
.grid{display:grid;gap:14px}
@media(min-width:680px){.grid.c3{grid-template-columns:1fr 1fr 1fr}.grid.c2{grid-template-columns:1fr 1fr}}
.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:18px}
.card h3{margin:0 0 6px;font-size:16px}
.card p{margin:0;color:var(--mut);font-size:13px;line-height:1.5}
.card.click{cursor:pointer;transition:.15s}
.card.click:hover{border-color:#3a3a44;transform:translateY(-1px)}
.tag{display:inline-block;border-radius:999px;padding:5px 12px;font-size:11px;font-weight:700;color:#0a0a0b}
.row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.sp{flex:1}
.muted{color:var(--mut)}
.opts{display:flex;gap:10px;margin:16px 0}
.seg{flex:1;text-align:center;border:1px solid var(--line);border-radius:10px;padding:10px;font-size:12px;cursor:pointer;color:var(--mut)}
.seg.on{background:var(--panel2);color:var(--txt);border-color:#3a3a44}
.toggle{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--mut);cursor:pointer;user-select:none}
.toggle .box{width:38px;height:22px;border-radius:999px;background:#2a2a30;position:relative;transition:.15s}
.toggle .box i{position:absolute;top:2px;left:2px;width:18px;height:18px;border-radius:50%;background:#777;transition:.15s}
.toggle.on .box{background:var(--acc)}
.toggle.on .box i{left:18px;background:#fff}
.progress{height:4px;background:var(--panel2);border-radius:999px;overflow:hidden;margin:10px 0 22px}
.progress i{display:block;height:100%;background:#fff;transition:.3s}
.qtag{margin-bottom:14px}
.qtext{font-size:21px;line-height:1.35;font-weight:600;margin:0 0 22px}
.choice{display:flex;gap:14px;align-items:flex-start;border:1px solid var(--line);background:var(--panel);border-radius:14px;padding:16px 18px;margin-bottom:12px;cursor:pointer;transition:.12s}
.choice:hover{border-color:#3a3a44}
.choice .k{flex:none;width:26px;height:26px;border-radius:50%;border:1px solid var(--line);display:flex;align-items:center;justify-content:center;font-size:12px;color:var(--mut)}
.choice .t{font-size:15px;line-height:1.45}
.choice.sel{border-color:#5a5a66;background:var(--panel2)}
.choice.correct{border-color:var(--ok);background:rgba(63,179,127,.08)}
.choice.wrong{border-color:var(--bad);background:rgba(224,87,75,.08)}
.choice .badge{margin-left:auto;font-size:11px;font-weight:700;display:flex;align-items:center;gap:6px}
.expl{border:1px solid var(--line);background:var(--panel2);border-radius:12px;padding:14px 16px;margin-top:6px;font-size:13.5px;line-height:1.55;color:#cfcfd6}
.expl b{color:var(--ok)}
.foot{display:flex;align-items:center;gap:12px;margin-top:18px}
.score-big{font-size:64px;font-weight:800;line-height:1}
.pill{display:inline-block;padding:6px 14px;border-radius:999px;font-weight:700;font-size:14px}
.pill.pass{background:rgba(63,179,127,.15);color:var(--ok);border:1px solid rgba(63,179,127,.4)}
.pill.fail{background:rgba(224,87,75,.15);color:var(--bad);border:1px solid rgba(224,87,75,.4)}
.bar{height:8px;background:var(--panel2);border-radius:999px;overflow:hidden}
.bar i{display:block;height:100%}
.dgrid{display:grid;grid-template-columns:auto 1fr auto;gap:10px 14px;align-items:center;font-size:13px}
.rev{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-bottom:10px;background:var(--panel)}
.rev .qh{font-size:14px;font-weight:600;margin:8px 0}
.rev .opt{font-size:13px;padding:4px 0;color:var(--mut)}
.rev .opt.c{color:var(--ok)}
.rev .opt.x{color:var(--bad)}
.hist{font-size:13px}
.hist .hrow{display:flex;gap:12px;align-items:center;padding:8px 0;border-bottom:1px solid var(--line)}
small.k{color:var(--mut);font-size:11px}
a.link{color:var(--acc);cursor:pointer}
.lesson{margin:10px 0 26px}
.lblk{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:12px}
.lblk h4{margin:0 0 10px;font-size:15px;color:var(--txt)}
.lblk ul{margin:0;padding-left:18px}
.lblk li{color:#cfcfd6;font-size:14px;line-height:1.6;margin-bottom:7px}
.lblk li:last-child{margin-bottom:0}
.lblk li b{color:var(--txt);font-weight:700}
.worked .wq{font-size:15px;font-weight:600;margin:0 0 12px;line-height:1.42}
.wrow{border:1px solid var(--line);border-radius:10px;padding:11px 13px;margin-bottom:9px;font-size:13.5px;line-height:1.55;color:#cfcfd6}
.wrow:last-child{margin-bottom:0}
.wrow.c{border-color:var(--ok);background:rgba(63,179,127,.07)}
.wrow.x{border-color:var(--bad);background:rgba(224,87,75,.05)}
.wrow .wk{font-weight:700;margin-right:4px}
.wrow .wk.c{color:var(--ok)}
.wrow .wk.x{color:var(--bad)}
.wrow .wy{display:block;margin-top:6px;color:var(--mut);font-size:13px}
.wrow .wy b{color:var(--txt)}
</style>
</head>
<body>
<header class="top">
  <div class="brand"><b class="mono">brq</b><span class="sub mono">CLAUDE ARCHITECT · EXAM TRAINER</span></div>
  <div class="row">
    <button class="btn ghost mono" onclick="go('home')">HOME</button>
    <button class="btn ghost mono" onclick="go('history')">HISTÓRICO</button>
  </div>
</header>
<div class="wrap" id="app"></div>

<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const Q = DATA.questions, M = DATA.meta, D = M.domains, LESSONS = DATA.lessons||{};
const LS_HIST='cca_history', LS_OPT='cca_opts';
const DOMAIN_SESSION_N=10; // padrão fixo de perguntas por sessão no treino por domínio
let opts = loadOpts();
let state = null; // active quiz

function loadOpts(){ try{return Object.assign({shuffleQ:true,shuffleOpt:true,instant:false,difficulty:'normal'}, JSON.parse(localStorage.getItem(LS_OPT)||'{}'));}catch(e){return {shuffleQ:true,shuffleOpt:true,instant:false,difficulty:'normal'};} }
function saveOpts(){ localStorage.setItem(LS_OPT, JSON.stringify(opts)); }
function hist(){ try{return JSON.parse(localStorage.getItem(LS_HIST)||'[]');}catch(e){return [];} }
function pushHist(r){ const h=hist(); h.unshift(r); localStorage.setItem(LS_HIST, JSON.stringify(h.slice(0,50))); }
function shuffle(a){ a=a.slice(); for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];} return a; }
function spreadByAnswer(items){
  // reordena para que a letra da resposta certa nunca se repita em questões consecutivas
  const buckets={A:[],B:[],C:[],D:[]};
  items.forEach(it=>buckets[it.q.answer].push(it));
  const out=[]; let last=null;
  for(let n=0;n<items.length;n++){
    let cand=['A','B','C','D'].filter(l=>buckets[l].length>0 && l!==last);
    if(!cand.length) cand=['A','B','C','D'].filter(l=>buckets[l].length>0);
    const mx=Math.max(...cand.map(l=>buckets[l].length));
    const top=cand.filter(l=>buckets[l].length===mx);
    const l=top[Math.floor(Math.random()*top.length)];
    out.push(buckets[l].shift()); last=l;
  }
  return out;
}
function pool(){ return opts.difficulty==='all' ? Q.slice() : Q.filter(q=>q.difficulty===opts.difficulty); }
function byDomain(d){ return pool().filter(q=>q.domain===d); }
function el(h){ const t=document.createElement('template'); t.innerHTML=h.trim(); return t.content.firstChild; }
function esc(s){ return (s+'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
const app = ()=>document.getElementById('app');

function go(view, arg){ if(view==='home') renderHome(); else if(view==='history') renderHistory(); else if(view==='quiz') renderQuiz(); else if(view==='result') renderResult(); else if(view==='lesson') renderLesson(arg); }

/* ---------- HOME ---------- */
function renderHome(){
  const h = hist();
  const best = h.length? Math.max(...h.map(x=>x.scaled)) : null;
  const last = h.length? h[0].scaled : null;
  const nNorm=Q.filter(q=>q.difficulty==='normal').length, nHard=Q.filter(q=>q.difficulty==='hard').length;
  const P=pool(); const poolN=P.length;
  const counts = {}; P.forEach(q=>counts[q.domain]=(counts[q.domain]||0)+1);
  const diffLabel = opts.difficulty==='hard'?'Hard':(opts.difficulty==='all'?'Ambas':'Normal');
  const totByDom={}; Q.forEach(q=>totByDom[q.domain]=(totByDom[q.domain]||0)+1);
  let domCards = Object.keys(D).map(k=>`
    <div class="card click" onclick="go('lesson','${k}')">
      <span class="tag mono" style="background:${D[k].color}">${D[k].tag}</span>
      <h3 style="margin-top:12px">${esc(D[k].name)}</h3>
      <p>📘 Aula + ${totByDom[k]||0} questões · peso ${Math.round(D[k].weight*100)}%</p>
    </div>`).join('');
  const dseg=(key,label)=>`<div class="seg ${opts.difficulty===key?'on':''}" onclick="setDiff('${key}')">${label}</div>`;
  app().innerHTML = `
    <h1>Treino para a certificação</h1>
    <p class="lead">Banco: ${nNorm} normais + ${nHard} hard = ${Q.length} · nota na escala ${M.scaleMin}–${M.scaleMax} · corte ${M.passMark} · pesos por domínio iguais aos do exame.</p>

    <div class="grid c3" style="margin-bottom:14px">
      <div class="card"><small class="k mono">MELHOR NOTA</small><div class="score-big" style="font-size:40px;margin-top:6px">${best??'—'}</div></div>
      <div class="card"><small class="k mono">ÚLTIMA NOTA</small><div class="score-big" style="font-size:40px;margin-top:6px">${last??'—'}</div></div>
      <div class="card"><small class="k mono">SIMULADOS FEITOS</small><div class="score-big" style="font-size:40px;margin-top:6px">${h.length}</div></div>
    </div>

    <div class="card" style="margin-bottom:18px">
      <small class="k mono">DIFICULDADE</small>
      <div class="opts" style="margin:10px 0 4px">${dseg('normal','Normal · '+nNorm)}${dseg('hard','Hard · '+nHard)}${dseg('all','Ambas · '+Q.length)}</div>
      <p class="muted" style="font-size:12px;margin:6px 0 14px">${opts.difficulty==='hard'?'Hard: duas opções defensáveis, melhor-vs-segundo-melhor; exige decidir pela restrição do enunciado.':(opts.difficulty==='all'?'Mistura normais e hard.':'Normal (Foundations): uma resposta claramente certa.')}</p>
      <div class="row" style="gap:18px">
        <label class="toggle ${opts.shuffleQ?'on':''}" onclick="tog('shuffleQ')"><span class="box"><i></i></span>Embaralhar ordem das questões</label>
        <label class="toggle ${opts.instant?'on':''}" onclick="tog('instant')"><span class="box"><i></i></span>Feedback imediato</label>
      </div>
    </div>

    <h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:6px 0 12px">SIMULADO PONDERADO (distribuído por peso)</h3>
    <div class="grid c3" style="margin-bottom:22px">
      <div class="card click" onclick="startWeighted(15)"><h3>Rápido · 15</h3><p>Amostra ponderada de 15 questões. ~10 min.</p></div>
      <div class="card click" onclick="startWeighted(30)"><h3>Médio · 30</h3><p>Amostra ponderada de 30 questões. ~20 min.</p></div>
      <div class="card click" onclick="startWeighted(45)"><h3>Longo · 45</h3><p>Amostra ponderada de 45 questões. ~30 min.</p></div>
    </div>

    <h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:6px 0 12px">PROVA COMPLETA</h3>
    <div class="grid c2" style="margin-bottom:22px">
      <div class="card click" onclick="startAll()"><h3>Banco inteiro · ${poolN}</h3><p>Todas as questões (${diffLabel}), ponderadas por domínio no resultado.</p></div>
      <div class="card click" onclick="startWeighted(60)"><h3>Simulado oficial · ${Math.min(60,poolN)}</h3><p>Proporção do exame (${diffLabel}); usa até ${poolN} disponíveis.</p></div>
    </div>

    <h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:6px 0 4px">TREINO POR DOMÍNIO</h3>
    <p class="lead" style="margin:0 0 12px">Cada domínio abre uma aula com o resumo do tema e, no fim, a sessão de perguntas (Normais, Hard ou Ambas).</p>
    <div class="grid c2">${domCards}</div>
  `;
}
function tog(k){ opts[k]=!opts[k]; saveOpts(); renderHome(); }

/* ---------- QUIZ SETUP ---------- */
function weightedSample(n){
  // allocate counts per domain by weight, capped by availability
  const keys = Object.keys(D);
  let alloc = {}; let sum = keys.reduce((s,k)=>s+D[k].weight,0);
  let total=0;
  keys.forEach(k=>{ alloc[k]=Math.round(n*D[k].weight/sum); total+=alloc[k]; });
  // fix rounding to hit n
  let diff=n-total; let i=0;
  while(diff!==0){ const k=keys[i%keys.length]; if(diff>0){alloc[k]++;diff--;} else if(alloc[k]>0){alloc[k]--;diff++;} i++; if(i>1000)break; }
  let picked=[];
  keys.forEach(k=>{ const pool=shuffle(byDomain(k)); picked=picked.concat(pool.slice(0, Math.min(alloc[k], pool.length))); });
  return picked;
}
function buildState(list, label){
  let qs = opts.shuffleQ ? shuffle(list) : list.slice();
  let items = qs.map(q=>({ q, order:['A','B','C','D'], picked:null, revealed:false }));
  // evita que a resposta certa caia na mesma letra de duas questões seguidas
  if(opts.shuffleQ) items = spreadByAnswer(items);
  state = { label, i:0, items };
  go('quiz');
}
function startWeighted(n){ buildState(weightedSample(n), `Simulado ponderado · ${n}`); }
function startAll(){ const p=pool(); buildState(p, `Prova completa · ${p.length}`); }
function setDiff(d){ opts.difficulty=d; saveOpts(); renderHome(); }
function startDomain(k){ buildState(byDomain(k), `Domínio ${D[k].tag}`); }
function startDomainDiff(k,diff){
  let list=Q.filter(q=>q.domain===k && (diff==='all'||q.difficulty===diff));
  if(!list.length){ alert('Sem questões nesta dificuldade para este domínio.'); return; }
  list=shuffle(list).slice(0, DOMAIN_SESSION_N); // amostra o padrão fixo da sessão
  const dl = diff==='hard'?'Hard':(diff==='all'?'Ambas':'Normais');
  buildState(list, `Domínio ${D[k].tag} · ${dl} · ${list.length}q`);
}

/* ---------- AULA (lesson) ---------- */
function workedBlock(k){
  const ws=(LESSONS[k]&&LESSONS[k].worked)||[];
  if(!ws.length) return '';
  const body=ws.map((w,i)=>{
    const rows=['A','B','C','D'].map(L=>{
      const ok=L===w.answer;
      return `<div class="wrow ${ok?'c':'x'}"><span class="wk ${ok?'c':'x'}">${L}) ${ok?'✓':'✗'}</span> ${w.options[L]}<span class="wy">${w.breakdown[L]}</span></div>`;
    }).join('');
    return `<div class="lblk worked"><div style="margin-bottom:9px"><span class="tag mono" style="background:var(--bad)">HARD</span></div><p class="wq">${i+1}. ${w.q}</p>${rows}</div>`;
  }).join('');
  return `<h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:20px 0 4px">QUESTÕES RESOLVIDAS · HARD</h3>
    <p class="lead" style="margin:0 0 12px">Exemplos destrinchados (não entram na sua nota) — veja por que cada alternativa está certa ou errada.</p>${body}`;
}
function renderLesson(k){
  const dom=D[k], L=LESSONS[k];
  const nNorm=Q.filter(q=>q.domain===k&&q.difficulty==='normal').length;
  const nHard=Q.filter(q=>q.domain===k&&q.difficulty==='hard').length;
  if(!L){ startDomainDiff(k,'all'); return; }
  const secs = L.sections.map(s=>`
    <div class="lblk"><h4>${esc(s.h)}</h4>
      <ul>${s.points.map(p=>`<li>${p}</li>`).join('')}</ul></div>`).join('');
  const card=(diff,title,desc,n)=>`<div class="card click" onclick="startDomainDiff('${k}','${diff}')">
      <h3>${title} · ${n}</h3><p>${desc}</p></div>`;
  app().innerHTML = `
    <div class="row" style="margin-bottom:10px"><button class="btn ghost mono" onclick="go('home')">← HOME</button></div>
    <div class="qtag"><span class="tag mono" style="background:${dom.color}">${dom.tag}</span>
      <span class="tag mono" style="background:var(--panel2);color:var(--mut);border:1px solid var(--line)">📘 AULA · peso ${Math.round(dom.weight*100)}%</span></div>
    <h1 style="margin:8px 0 4px">${esc(dom.name)}</h1>
    <p class="lead">${L.intro}</p>
    <div class="lesson">${secs}</div>
    ${workedBlock(k)}
    <h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:6px 0 4px">SESSÃO DE PERGUNTAS</h3>
    <p class="lead" style="margin:0 0 14px">Agora pratique este domínio. Cada sessão tem ${DOMAIN_SESSION_N} perguntas, sorteadas do banco. Escolha a dificuldade:</p>
    <div class="grid c3" style="margin-bottom:10px">
      ${card('normal','Normais',`Uma resposta claramente certa (Foundations). ${nNorm} no banco.`,Math.min(DOMAIN_SESSION_N,nNorm))}
      ${card('hard','Hard',`Duas opções defensáveis; decida pela restrição. ${nHard} no banco.`,Math.min(DOMAIN_SESSION_N,nHard))}
      ${card('all','Ambas',`Mistura normais e hard. ${nNorm+nHard} no banco.`,Math.min(DOMAIN_SESSION_N,nNorm+nHard))}
    </div>`;
  window.scrollTo(0,0);
}

/* ---------- QUIZ ---------- */
function renderQuiz(){
  const s=state, it=s.items[s.i], q=it.q, dom=D[q.domain];
  const pct=Math.round((s.i)/s.items.length*100);
  let choices = it.order.map((key,idx)=>{
    const dispLetter='ABCD'[idx];
    let cls='choice';
    if(it.revealed){
      if(key===q.answer) cls+=' correct';
      else if(key===it.picked) cls+=' wrong';
    } else if(it.picked===key) cls+=' sel';
    let badge='';
    if(it.revealed && key===q.answer) badge='<span class="badge" style="color:var(--ok)">✓ CORRETA</span>';
    else if(it.revealed && key===it.picked) badge='<span class="badge" style="color:var(--bad)">✗ SUA RESPOSTA</span>';
    return `<div class="${cls}" onclick="pick('${key}')">
        <div class="k mono">${dispLetter}</div>
        <div class="t">${esc(q.options[key])}</div>${badge}
      </div>`;
  }).join('');
  let explBlock = it.revealed ? `<div class="expl"><b>Resposta correta: ${q.answer}.</b> ${esc(q.explanation)}</div>` : '';
  const lastLabel = s.i===s.items.length-1?'FINALIZAR':'PRÓXIMA →';
  // com feedback imediato: 1º clique seleciona (reversível), CORRIGIR revela/trava, depois PRÓXIMA avança.
  let actionBtn;
  if(opts.instant && !it.revealed){
    actionBtn = `<button class="btn primary mono" id="nextBtn" onclick="reveal()" ${it.picked?'':'disabled'}>CORRIGIR</button>`;
  } else if(opts.instant){
    actionBtn = `<button class="btn primary mono" id="nextBtn" onclick="advance()">${lastLabel}</button>`;
  } else {
    actionBtn = `<button class="btn primary mono" id="nextBtn" onclick="nextQ()" ${it.picked?'':'disabled'}>${lastLabel}</button>`;
  }
  app().innerHTML = `
    <div class="row" style="margin-bottom:6px">
      <button class="btn ghost mono" onclick="quitQuiz()">← SAIR</button>
      <span class="muted mono" style="font-size:12px">${esc(s.label)}</span>
      <span class="sp"></span>
      <span class="mono" style="font-size:14px">Q ${s.i+1} / ${s.items.length}</span>
    </div>
    <div class="progress"><i style="width:${pct}%"></i></div>
    <div class="qtag"><span class="tag mono" style="background:${dom.color}">${dom.tag}</span>${q.difficulty==='hard'?' <span class="tag mono" style="background:#e0574b">HARD</span>':''}</div>
    <p class="qtext">${esc(q.q)}</p>
    ${choices}
    ${explBlock}
    <div class="foot">
      <span class="sp"></span>
      ${ s.i>0 ? '<button class="btn ghost mono" onclick="prevQ()">← ANTERIOR</button>':''}
      ${actionBtn}
    </div>
  `;
}
function pick(key){
  const it=state.items[state.i];
  if(it.revealed) return;       // já corrigida: trava a escolha
  it.picked=key;                // só seleciona (reversível enquanto não corrige)
  renderQuiz();
}
function reveal(){              // feedback imediato: CORRIGIR revela e trava a resposta
  const it=state.items[state.i];
  if(!it.picked || it.revealed) return;
  it.revealed=true;
  renderQuiz();
}
function advance(){            // avança sem mexer no estado de revelado
  if(state.i < state.items.length-1){ state.i++; renderQuiz(); }
  else finish();
}
function nextQ(){              // modo sem feedback imediato: trava e avança num clique só
  const it=state.items[state.i];
  if(!it.picked) return;
  it.revealed=true;
  advance();
}
function prevQ(){ if(state.i>0){state.i--; renderQuiz();} }
function quitQuiz(){ if(confirm('Sair do simulado? O progresso atual será descartado.')){ state=null; go('home'); } }

/* ---------- RESULT ---------- */
function computeScore(){
  const perDom={}; // {D1:{c,t}}
  state.items.forEach(it=>{
    const d=it.q.domain; perDom[d]=perDom[d]||{c:0,t:0};
    perDom[d].t++; if(it.picked===it.q.answer) perDom[d].c++;
  });
  let presentWeight=0, acc=0, totalC=0, totalT=0;
  Object.keys(perDom).forEach(d=>{ presentWeight+=D[d].weight; });
  Object.keys(perDom).forEach(d=>{
    const r=perDom[d].c/perDom[d].t;
    acc += r * (D[d].weight/presentWeight);
    totalC+=perDom[d].c; totalT+=perDom[d].t;
  });
  const scaled = Math.round(M.scaleMin + acc*(M.scaleMax-M.scaleMin));
  return { perDom, weightedPct:acc, scaled, pass:scaled>=M.passMark, totalC, totalT };
}
function finish(){
  const r=computeScore();
  pushHist({ date:new Date().toISOString(), label:state.label, scaled:r.scaled, pass:r.pass, correct:r.totalC, total:r.totalT });
  state._result=r;
  go('result');
}
function revCard(it,idx){
  const q=it.q, ok=it.picked===q.answer;
  const pickedTxt = it.picked? it.picked : '—';
  let optLines = ['A','B','C','D'].map(k=>{
    let c=''; if(k===q.answer)c='c'; else if(k===it.picked && !ok)c='x';
    const mark = k===q.answer?'✓':(k===it.picked?'✗':' ');
    return `<div class="opt ${c}">${mark} ${k}) ${esc(q.options[k])}</div>`;
  }).join('');
  return `<div class="rev" style="border-left:3px solid ${ok?'var(--ok)':'var(--bad)'}">
    <div class="row"><span class="tag mono" style="background:${D[q.domain].color}">${D[q.domain].tag}</span>${q.difficulty==='hard'?'<span class="tag mono" style="background:#e0574b">HARD</span>':''}
      <span class="sp"></span>
      <span class="mono" style="color:${ok?'var(--ok)':'var(--bad)'}">${ok?'✓ ACERTOU':'✗ ERROU'}</span></div>
    <div class="qh">${idx+1}. ${esc(q.q)}</div>
    ${optLines}
    <div class="expl"><b style="color:${ok?'var(--ok)':'var(--bad)'}">Sua resposta: ${pickedTxt} ${ok?'(correta)':'· Correta: '+q.answer}.</b> ${esc(q.explanation)}</div>
  </div>`;
}
function renderReview(){
  const s=state;
  const f = s._revFilter||'all';
  const tagged = s.items.map((it,idx)=>({it,idx,ok:it.picked===it.q.answer}));
  const wrong = tagged.filter(t=>!t.ok), right = tagged.filter(t=>t.ok);
  let list;
  if(f==='wrong') list=wrong;
  else if(f==='right') list=right;
  else list=wrong.concat(right); // erros primeiro
  let body;
  if(!list.length){ body = `<p class="lead">Nada para mostrar neste filtro.</p>`; }
  else if(f==='all'){
    body = (wrong.length? `<h3 class="mono" style="color:var(--bad);font-size:12px;letter-spacing:.1em;margin:18px 0 10px">❌ QUE VOCÊ ERROU (${wrong.length})</h3>`+wrong.map(t=>revCard(t.it,t.idx)).join(''):'')
         + (right.length? `<h3 class="mono" style="color:var(--ok);font-size:12px;letter-spacing:.1em;margin:22px 0 10px">✅ QUE VOCÊ ACERTOU (${right.length})</h3>`+right.map(t=>revCard(t.it,t.idx)).join(''):'');
  } else {
    body = list.map(t=>revCard(t.it,t.idx)).join('');
  }
  const seg=(key,label)=>`<div class="seg ${f===key?'on':''}" onclick="setRevFilter('${key}')">${label}</div>`;
  return `
    <div class="row" style="margin:6px 0 4px"><h3 class="mono" style="color:var(--mut);font-size:12px;letter-spacing:.1em;margin:0">GABARITO COMENTADO</h3></div>
    <div class="opts">${seg('all','Todas')}${seg('wrong','Só erros ('+wrong.length+')')}${seg('right','Só acertos ('+right.length+')')}</div>
    <div id="revBody">${body}</div>`;
}
function setRevFilter(f){ state._revFilter=f; document.getElementById('reviewWrap').innerHTML=renderReview(); }
function renderResult(){
  const s=state, r=s._result;
  let doms = Object.keys(r.perDom).map(d=>{
    const pd=r.perDom[d], pct=Math.round(pd.c/pd.t*100);
    return `<span class="tag mono" style="background:${D[d].color};justify-self:start">${D[d].tag}</span>
            <div class="bar"><i style="width:${pct}%;background:${D[d].color}"></i></div>
            <span class="mono">${pd.c}/${pd.t}</span>`;
  }).join('');
  const wrongN = s.items.filter(it=>it.picked!==it.q.answer).length;
  app().innerHTML = `
    <div class="row"><button class="btn ghost mono" onclick="go('home')">← HOME</button><span class="sp"></span><span class="muted mono" style="font-size:12px">${esc(s.label)}</span></div>
    <div class="card" style="margin:14px 0;text-align:center;padding:30px">
      <small class="k mono">NOTA FINAL · ESCALA ${M.scaleMin}–${M.scaleMax}</small>
      <div class="score-big" style="margin:12px 0;color:${r.pass?'var(--ok)':'var(--bad)'}">${r.scaled}</div>
      <span class="pill ${r.pass?'pass':'fail'}">${r.pass?'✅ APROVADO':'❌ REPROVADO'} · corte ${M.passMark}</span>
      <p class="muted" style="margin-top:14px">${r.totalC} de ${r.totalT} corretas · ${wrongN} erradas · ${Math.round(r.weightedPct*100)}% ponderado</p>
    </div>
    <div class="card" style="margin-bottom:18px">
      <small class="k mono">DESEMPENHO POR DOMÍNIO</small>
      <div class="dgrid" style="margin-top:14px">${doms}</div>
    </div>
    <div class="row" style="margin-bottom:8px">
      <button class="btn primary mono" onclick="retrySame()">REFAZER ESTE</button>
      ${wrongN? '<button class="btn mono" onclick="retryWrong()">TREINAR SÓ OS ERROS ('+wrongN+')</button>':''}
      <button class="btn mono" onclick="go('home')">NOVO SIMULADO</button>
    </div>
    <div id="reviewWrap">${renderReview()}</div>
  `;
  window.scrollTo(0,0);
}
function retryWrong(){ const list=state.items.filter(it=>it.picked!==it.q.answer).map(it=>it.q); if(!list.length)return; buildState(list, 'Revisão dos erros · '+list.length); }
function retrySame(){ const list=state.items.map(it=>it.q); const lbl=state.label; buildState(list,lbl); }

/* ---------- HISTORY ---------- */
function renderHistory(){
  const h=hist();
  let rows = h.length? h.map(x=>{
    const d=new Date(x.date);
    return `<div class="hrow"><span class="mono" style="color:${x.pass?'var(--ok)':'var(--bad)'};width:60px">${x.scaled}</span>
      <span>${esc(x.label)}</span><span class="sp"></span>
      <span class="muted">${x.correct}/${x.total}</span>
      <span class="muted mono" style="font-size:11px">${d.toLocaleDateString('pt-BR')} ${d.toLocaleTimeString('pt-BR',{hour:'2-digit',minute:'2-digit'})}</span></div>`;
  }).join('') : '<p class="lead">Nenhum simulado registrado ainda.</p>';
  app().innerHTML = `
    <div class="row"><button class="btn ghost mono" onclick="go('home')">← HOME</button>
      <span class="sp"></span>${h.length?'<button class="btn mono" onclick="clearHist()">LIMPAR HISTÓRICO</button>':''}</div>
    <h1 style="margin-top:14px">Histórico</h1>
    <p class="lead">Suas notas ficam salvas neste navegador (localStorage).</p>
    <div class="card hist">${rows}</div>
  `;
}
function clearHist(){ if(confirm('Apagar todo o histórico?')){ localStorage.removeItem(LS_HIST); renderHistory(); } }

renderHome();
</script>
</body>
</html>
'''

html = HTML.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)
print("Wrote index.html (", len(html), "bytes )")
