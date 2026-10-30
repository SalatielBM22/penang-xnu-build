# C04 — candidato de CI diagnóstico, 2026-10-30

Este candidato coleta configuração; não contém uma correção do kernel.
O patch QEMU_VIRT permanece com SHA-256
`2fbebcac6ad73a1c78f4fc7b437edc1067e34509d00ca2e5e798d680e50fdab2`.
Portanto, espera-se reproduzir os sete erros históricos de `pmap.o`.

A mudança no workflow executa `scripts/c04_capture_pmap.mjs` mesmo após a
falha do build. O coletor procura exatamente um `pmap.o.json` do QEMU_VIRT,
usa seu vetor `arguments` sem shell e preserva seu diretório e includes.
Aceita somente o Clang Xcode 16.4 fixado, Cortex-A76 e ABI ARM64 nativa.
Remove saídas de objeto/dependências antes de solicitar `-E -dM`.

O artefato novo contém a invocação, hashes e uma lista restrita de macros
pmap/CPU, distinguindo macro indefinida de macro definida como zero.
Não publica o dump completo de macros nem texto expandido de headers SDK/KDK.
O resultado nunca concede `C04 PASS`: pré-processamento não compila `pmap.o`.
A falha real do passo de build continua determinando a conclusão do job.

Validação local: Node Windows 24.22.1, 11 testes do leitor histórico e
13 testes do coletor, incluindo fixtures explícitas de argv/macros.
O coletor foi executado sem database local e retornou exit 2 / CAPTURE_BLOCKED,
com `macros_valid=false`. Nenhum Clang macOS foi executado localmente.
O formato real do database e o ambiente Node do runner ainda precisam da
execução diagnóstica; ausência ou formato inesperado devem bloquear a coleta.

Reprodução local, com os inputs históricos preservados em `build/c04-inputs`:

```powershell
node --test --test-isolation=none scripts/test_c04_ci_evidence.mjs scripts/test_c04_capture_pmap.mjs
node scripts/c04_ci_evidence.mjs build/c04-inputs/build.log ../integration/reports/C04-SOURCE-INPUTS.json build/c04-source build/c04-inputs/ci-audit-recheck.json
```

As fontes públicas locais são snapshots ignorados pelo Git. Seus 16 pins e
hashes estão em `../integration/reports/C04-SOURCE-INPUTS.json` e
`C04-CI-AUDIT.json`; não são uma árvore XNU completa nem headers gerados do CI.

Publicação permanece pendente. Uma autorização futura deve especificar o
SHA completo deste candidato e `refs/heads/exp/p0.1d-qemu-virt`, com um push
fast-forward e somente a execução provocada por ele, sem dispatch ou rerun.
O custo proposto é um job `macos-15`, com o teto existente de 180 minutos;
a etapa adicional limita o Clang de pré-processamento a 60 segundos.
Não há estimativa monetária verificada. Nenhuma execução foi solicitada.
