# Declaração de uso de IA generativa

**Ferramenta/modelo:** Claude (Anthropic), via claude.ai e Claude Code.
**Datas de uso:** 07/11/2026 (laboratório, relatório e slides, por Mateus) e 10/11/2026 (organização do repositório e do vídeo, por Mikael).

**Finalidade:** gerar a primeira versão dos scripts do laboratório (coleta do ambiente, namespaces e read-only, carga de CPU, medição no cgroup, execuções e resumo), o passo a passo de execução no WSL2, interpretar os registros, e redigir o relatório, os slides e o roteiro. **Nenhum número do relatório veio da IA:** todas as medições saíram das execuções no computador da equipe e estão em `registros/`.

## Prompts relevantes (resumidos)

1. "Analise o enunciado da Atividade 3 e crie um guia do zero, com scripts, para rodar tudo no WSL2 em uma máquina só, incluindo o passo a passo dos comandos no terminal."
2. "Interprete os dois pilotos e diga qual N usar nas seis execuções; depois analise os registros reais copiados do WSL2."
3. "Escreva o relatório com os nomes da equipe, seguindo as seções do enunciado, e crie a apresentação e o roteiro de falas."

## Sugestões e como foram verificadas

| Sugestão da IA | Decisão | Como verificamos |
|---|---|---|
| Ler `/sys/fs/cgroup/cpu.max` de dentro do contêiner para confirmar a quota | Adotada | Documentação do cgroup v2 e valor `50000 100000` registrado em C1 |
| `--memory-swap 256m` igual a `--memory` para RAM+swap = 256 MiB | Adotada | Documentação "Resource constraints" do Docker e `memory.swap.max = 0` no registro |
| Carga com checksum conferido por fórmula fechada | Adotada | `correto: True` nas seis execuções |
| Instalar matplotlib com `pip install -r requirements.txt` | Corrigida | No Ubuntu, o `pip` fora de ambiente virtual é bloqueado; usamos `apt-get install python3-matplotlib` |
| Ler os namespaces dos processos pelo host sem privilégio | Corrigida | O `/proc` do terminal não lia os namespaces dos processos do root; a rodada de 17:14:53, com `sudo`, é a usada |
| N = 79 milhões, sugerido pelo `run_experimentos.sh` | Rejeitada | O script supõe C1 = 2 × C2, mas o primeiro piloto deu C1 com 3,3 vezes o tempo de C2; um segundo piloto com N = 60 milhões deu C1 em 22,4 s, e esse foi o N usado |

## Adaptações

Os scripts usados são os da pasta `atividade3/`, gerados com IA e revisados pela equipe, com os mesmos papéis do kit de apoio do enunciado (coleta, namespaces e read-only, carga de CPU, execuções e resumo). Uma segunda versão do kit, com pastas e nomes diferentes, não foi usada nas medições e não está no repositório.
