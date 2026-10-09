# Relatório de entrega — Editor A4 Livre

Data: 9 de outubro de 2026.

## Atualização 1.1.0 — editor individual de figuras

Todas as ferramentas geométricas abrem automaticamente um editor individual ao concluir
o desenho. Cada figura guarda texto, fonte, alinhamento horizontal/vertical e cores
próprios. O editor possui prévia, centralização nas duas direções e botões Aplicar/Cancelar.
Duplo clique na figura ou o botão no painel reabre a edição. Cancelar preserva a figura
sem aplicar o rascunho; confirmar afeta somente o ID aberto e gera um comando no histórico.

Os textos acompanham transformação, duplicação, agrupamento, projeto e PDF. Retângulos
e elipses usam uma área interna; linhas/setas usam um rótulo central. As caixas de texto
livre continuam disponíveis. Projetos antigos mantêm suas formas sem rótulos inesperados.

Foram acrescentados 27 testes para abertura automática nas seis ferramentas, isolamento
entre figuras, cores, cancelamento, duplo clique, histórico, compatibilidade com projetos
antigos, validação dos novos campos, persistência e alinhamento no PDF. O autoteste do
executável também verifica o editor individual e a preservação do texto de outra figura.

**193 testes automatizados passaram** na validação completa da versão 1.1.0.
A prévia do editor e uma página com figuras de cores e textos diferentes foram
inspecionadas visualmente. O PDF dessa página foi renderizado com Poppler: textos
centralizados, cores individuais e rotação foram preservados.

## Funcionalidades implementadas

- Página A4 única, retrato/paisagem, zoom de 25% a 400%, réguas em centímetros,
  grade de 5 mm, magnetismo opcional e guias de alinhamento.
- Retângulo, quadrado, círculo, elipse, linha, seta, texto e imagens PNG/JPEG.
- Oito alças de tamanho visual constante, alteração independente das dimensões,
  proporção com Shift, rotação por alça e medidas exatas no painel.
- Texto multilinha, edição por duplo clique, fonte, tamanho, negrito, itálico,
  sublinhado, cor e alinhamento por caixa. Colagem de texto simples.
- Seleção individual, múltipla e por área; movimento conjunto; copiar, recortar,
  colar, duplicar, excluir; alinhamento e distribuição dos centros dos objetos.
- Grupos, escala proporcional de grupos, ordem de sobreposição, bloqueio e
  desbloqueio pela lista de camadas.
- Histórico QUndoStack com uma operação por gesto e até 150 operações.
- Projetos JSON `.a4livre` versão 1, imagens incorporadas, validação completa antes
  de abrir, salvamento atômico e confirmação de alterações não salvas.
- PDF A4 com geometria vetorial, texto, imagens e rotações, sem decorações do editor.
  Correção do MediaBox arredondado pelo Qt preserva as dimensões físicas exatas.
- Impressão por diálogo Windows, em tamanho real ou ajustada à área imprimível.
- Script de build Windows, pacote portátil, exemplo editável e documentação em português.

## Validação executada

Ambiente local: Windows 11, Python 3.14.5 de 64 bits, PySide6/Qt 6.12.0,
PyInstaller 6.22.3, pytest 9.1.1 e pytest-qt 4.5.0.

**166 testes automatizados passaram** na execução da versão 1.0.0, em 7,89 segundos.
O conjunto cobre os 14 cenários da especificação. Inclui 96 combinações de interação
real de mouse: oito alças, quatro rotações (0°, 45°, 90° e 270°) e três níveis de zoom
(25%, 100% e 400%). Os testes verificam a âncora oposta, dimensões e desfazer/refazer.

Também foram executados testes de teclado para texto, desbloqueio por duplo clique,
agrupamento/desagrupamento, cópia com novos IDs, persistência de medidas e imagens,
rejeição de arquivos inválidos e simulação de falha de escrita atômica. A impressão
foi exercitada com QPrinter em dispositivo PDF, tanto em tamanho real quanto com ajuste.

PDFs em retrato e paisagem foram reabertos com pypdf e PyMuPDF. Os testes conferem
MediaBox A4, posição e tamanho de retângulo vetorial, fonte de 18 pt, texto extraível,
imagem incorporada, fundo branco e ausência de rasterização da página inteira.
A página de demonstração foi renderizada com Poppler e inspecionada visualmente;
a captura da interface também foi inspecionada após as correções de tema e página.

O **executável Windows gerado passou no autoteste**, com código de saída zero e
`ok: true`. Dentro do próprio binário foram verificados redimensionamento pelo mouse
de forma rotacionada, desfazer/refazer, salvar/reabrir e exportar PDF vetorial A4.
O relatório reproduzível está em `docs/smoke-report.json`.

O build inicialmente capturou uma DLL ICU incompatível presente no PATH de outra
ferramenta. A causa foi reproduzida e corrigida isolando o PATH durante o empacotamento.
O script agora executa automaticamente o autoteste do pacote e rejeita builds que
falhem ou excedam 30 segundos. A entrega usa testes locais e autoteste do executável;
o workflow do GitHub Actions foi removido conforme solicitado.

## Limites e validações pendentes

- Impressão física não foi realizada: margens, escala e resultado em papel dependem
  do dispositivo e do driver. A saída por QPrinter em dispositivo PDF foi testada.
- O pacote foi executado neste Windows 11; não foi testado em todos os computadores,
  drivers, fontes e resoluções possíveis. O executável não possui assinatura digital.
- Formatação de texto aplica-se à caixa inteira; o conteúdo é texto simples.
  Texto que excede a caixa é recortado. Grupos redimensionam proporcionalmente.
- O aplicativo limita projetos a 100 MB, imagens a 25 MB/40 megapixels, 5.000 objetos
  e grupos com profundidade máxima de 20. A responsividade perto desses limites
  não foi validada por um teste de carga abrangente.
- Não há licença de distribuição escolhida para o código do projeto.

Não há recurso deliberadamente deixado como botão fictício na interface. As limitações
acima descrevem o comportamento e o alcance da validação realizada.

## Executar, testar e gerar o pacote

Consulte o `README.md`: ele contém os comandos de instalação, execução, testes e build.
Para uso portátil, extraia o ZIP e abra `EditorA4Livre.exe`, mantendo a pasta `_internal`
junto dele. O projeto de exemplo fica em `examples/demonstracao.a4livre`.
