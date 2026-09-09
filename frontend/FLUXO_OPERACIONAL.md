# VisionOps — fluxo operacional revisado em 09/09/2026

## Uso principal

Início → Revisar chamados → selecionar um chamado → conferir contexto e recomendação → salvar decisão.

- A abertura usa 01/12/2025, primeiro dia do holdout de dezembro, com 64 chamados elegíveis, 9 de risco alto e 34 moderado. Esses valores vêm de `/api/queue/sample`, não de constantes na interface.
- Início e fila compartilham o período aplicado. Alterar o formulário sem aplicar não troca o período dos resultados.
- Os filtros e a busca alteram a tabela e a exportação. Os cartões continuam mostrando o lote inteiro, como indicado nos rótulos.
- A seleção mostra a recomendação e a explicação ao lado da tabela; em telas estreitas, abaixo da lista.
- O registro chama `/api/actions`. Para uma fila histórica, a nota identifica um exercício; a aplicação não envia encaminhamentos a um sistema de atendimento externo.
- O contador de decisões inclui somente chamados daquele lote registrados na sessão atual. O armazenamento no backend é separado da base histórica. Não representa uma contagem de atrasos evitados.

## Planejamento

`/api/capacity` combina o forecast operacional com produtividade, ocupação, ausências e analistas disponíveis informados pelo usuário. Premissas iniciais são ilustrativas. Datas do forecast aparecem por extenso na interface; não correspondem à data atual.

`/api/optimization` distribui o volume previsto pelo peso histórico de violações dos produtos e aplica capacidade e limite por categoria. A porcentagem mostra o peso histórico incluído no plano. Não é uma previsão calibrada de violações evitadas. A curva inclui a capacidade escolhida pelo usuário, mesmo fora da grade original de sensibilidade.

## Investigação e modelos

- Diagnóstico compara grupos no histórico completo, separado do período da fila.
- Dados e modelos reúne monitoramento, métricas técnicas e qualidade da base. O aviso de revisão permanece visível na página inicial.
- O resultado observado dos chamados fica em uma seção de conferência, separado da recomendação que utiliza informações conhecidas na abertura.
- Contribuições dos fatores comparam o resultado com uma referência do modelo; não são causas demonstradas nem parcelas aditivas.
- Modelos e base de dados permanecem os existentes. Esta revisão modifica o fluxo de uso e a interpretação, não promete melhoria de precisão.

## Conferência

Build: `npm --prefix frontend run build`.
Persistência e ordenação: `python -m unittest tests.test_sprint4.TestFilaOperacional -v`.

Verificar no navegador: abertura, filtro de alto risco, troca de chamado, gravação de decisão, paginação, busca vazia, exportação do filtro, troca de data, cenário sem alto risco, recálculo da equipe, recálculo de produtos, diagnóstico, situação dos modelos, auditoria, avaliação individual, importação inválida e menu móvel.

O teste de interface intercepta gravações para não gerar eventos de teste no serviço público. A persistência real é testada separadamente em um banco local de teste.

## Inicialização no serviço gratuito

A API serializa a construção dos recursos em cache para impedir treinamentos duplicados durante chamadas simultâneas. O forecast operacional é carregado sem executar a extensão avançada. A extensão reutiliza a série e as métricas operacionais e só é calculada ao abrir seus detalhes. A página inicial carrega primeiro a fila; o histórico de volume é consultado ao expandir a seção correspondente.

Verificação após a correção: 33 testes Python aprovados, incluindo concorrência, modelos, métricas auditadas, fila e persistência. O build React também foi aprovado.
