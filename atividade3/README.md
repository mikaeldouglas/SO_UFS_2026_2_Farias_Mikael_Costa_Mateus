# Atividade 3: namespaces e cgroups em conteineres Linux

Equipe 07: Mateus do Rosario Costa, Cadmo Octavio Jose do Nascimento Neto, Douglas de Oliveira Deda, Lucas Conceicao Celestino, Mikael Douglas Santos Farias e Paulo Gabriel de Oliveira Cardoso. Contribuicoes em [CONTRIBUICOES.md](CONTRIBUICOES.md).
Video: https://drive.google.com/file/d/1qcASW57Jz6_aa4FHu9KA9FQ_YXvfqyIE/view (ordem de fala em [VIDEO.md](VIDEO.md)).
Commit da entrega: o commit que adicionou esta pasta (citado no relatorio). As medicoes foram feitas em 07/11/2026, antes do versionamento (`commit=sem_git` em `parametros.txt`).

## O que tem aqui

| Arquivo | Parte | Funcao |
|---|---|---|
| `coleta_ambiente.sh` | A | Registra terminal e daemon, baixa a imagem e grava o digest em `imagem.env` |
| `evidencia_ns_mount.sh` | B e D | Dois conteineres, handles de PID/mount/net, tabela CSV e teste read-only |
| `carga_cpu.py` | C | Trabalho fixo: soma de i*i mod 2^61-1, conferida pela formula fechada |
| `medir_cgroup.py` | C | Roda no conteiner; le `cpu.max`, `cpu.stat`, `memory.*`, `pids.*` antes e depois da carga |
| `run_experimentos.sh` | C | Piloto e as 6 execucoes (C1/C2 x 3), em ordem alternada |
| `resumo.py` | C | Gera `resultados.csv`, `resumo_condicoes.csv`, `tabela.md` e `grafico_c1_c2.png` |
| `limpeza.sh` | todas | Remove conteineres com o rotulo `so.atv3` que tenham sobrado |
| `registros/` | todas | Saidas brutas, nunca editadas a mao (exceto a anonimizacao abaixo) |
| `docs/` | A | Diagrama de camadas (`diagrama.mmd` e `diagrama_camadas.png`) |

## Imagem

`python:3.12-slim` fixada por digest. O digest usado esta em `imagem.env` (gerado por `coleta_ambiente.sh`):

```
IMAGEM_LAB=python@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54
```

## Preparacao

Requisitos no host: Linux com Docker (ou WSL2/Docker Desktop), cgroup v2, bash, python3 e matplotlib para o grafico.

```bash
sudo apt-get install -y python3-matplotlib     # so matplotlib
bash coleta_ambiente.sh                         # precisa de internet so aqui
. ./imagem.env && echo "$IMAGEM_LAB"
```

## Reproducao

```bash
# Parte B e D
bash evidencia_ns_mount.sh

# Parte C: piloto para escolher N (nao entra na comparacao)
export ITERACOES=20000000
PILOTO=1 bash run_experimentos.sh

# Congelar N e rodar as seis execucoes
export ITERACOES=60000000   # N congelado apos os dois pilotos
bash run_experimentos.sh
python3 resumo.py            # usa a sessao_* mais recente
```

Parametros fixos: C1 `--cpus 0.5`, C2 `--cpus 1.0`; ambas `--memory 256m --memory-swap 256m --pids-limit 64 --network none --user 65534:65534 --cap-drop ALL --security-opt no-new-privileges:true`. Limite interno de 60 s na carga e `timeout 90` no host.

## Coleta

| Evidencia | Onde fica |
|---|---|
| Ambiente | `registros/ambiente/ambiente_*.txt` |
| Namespaces | `registros/namespaces/<data>/A.txt`, `B.txt`, `visao_host.txt`, `namespaces.csv` |
| Read-only | `registros/readonly/<data>/readonly.txt`, `inspect_resumo.txt`, `host_antes.txt`, `host_depois.txt` |
| Execucoes | `registros/sessao_<data>/NN_Cx_rY.{json,meta,stderr}` e `parametros.txt` |
| Consolidado | `registros/sessao_<data>/resultados.csv`, `resumo_condicoes.csv`, `tabela.md`, `grafico_c1_c2.png` |

Sessao usada no relatorio: `registros/sessao_20261107_173636` (6 execucoes validas, N = 60 milhoes). Os pilotos estao em `registros/piloto_*`. Tentativas com erro ficam nas pastas e aparecem no CSV com `valida=False`.

## Limpeza

```bash
bash limpeza.sh                      # conteineres do laboratorio
docker image rm python:3.12-slim     # opcional
```

Os scripts ja removem os conteineres que criam, inclusive apos Ctrl+C.

## Diagrama de camadas

Ambiente real: Windows com WSL2 (VM utilitaria sobre o Hyper-V), Ubuntu 26.04.1 e Docker Engine 29.9.3 instalado dentro do Ubuntu. Um unico kernel Linux (`6.18.54.1-microsoft-standard-WSL2`) atende o terminal, o daemon e os conteineres. Fonte: [docs/diagrama.mmd](docs/diagrama.mmd); imagem: [docs/diagrama_camadas.png](docs/diagrama_camadas.png).

## Anonimizacao dos registros

Antes de publicar, o nome da maquina e o usuario do Linux foram trocados por `<host>` e `<usuario>` em `registros/ambiente/` e `registros/readonly/`. Nenhum numero foi alterado.

## Uso de IA

Ver [IA.md](IA.md).
