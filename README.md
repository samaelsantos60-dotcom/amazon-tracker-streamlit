# Monitor de métricas Amazon.es

Aplicação Python que consulta diariamente métricas de produtos da Amazon
Espanha através da API do Keepa e guarda os resultados numa base de dados SQLite.

## Configuração da `KEEPA_API_KEY` nos Secrets do Replit

1. Abra este projeto no Replit.
2. Na barra lateral esquerda, abra **Tools** e depois **Secrets**.
3. Clique em **+ New Secret** (ou **Add secret**).
4. No campo **Key**, escreva exatamente:

   ```text
   KEEPA_API_KEY
   ```

5. No campo **Value**, cole a sua chave pessoal da API do Keepa.
6. Clique em **Add secret** ou **Save**.
7. Reinicie a aplicação, se ela já estiver em execução.

O código lê o Secret automaticamente através de `os.getenv("KEEPA_API_KEY")`.
Não é necessário alterar o código nem colocar a chave num ficheiro. Não partilhe
o valor da chave em código, commits ou mensagens.

## Configurar alertas

Os alertas são enviados através de um bot do Telegram. Se os Secrets do
Telegram não estiverem configurados, os alertas são impressos de forma
destacada no terminal.

### Criar o bot no Telegram

1. Abra o Telegram e procure por **@BotFather**.
2. Envie `/newbot` e siga os passos apresentados.
3. Escolha um nome e um username terminado em `bot`.
4. O BotFather irá devolver um token. Guarde-o como Secret no Replit; não o
   publique nem o coloque no código.
5. Abra uma conversa com o bot recém-criado e envie-lhe `/start`.

Na barra lateral do Replit, abra **Tools > Secrets** e adicione:

```text
TELEGRAM_BOT_TOKEN = token fornecido pelo BotFather
TELEGRAM_CHAT_ID = ID do chat que deve receber os alertas
```

Para encontrar o **Chat ID**, envie primeiro `/start` ao bot e abra no browser:

```text
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getUpdates
```

Substitua `<TELEGRAM_BOT_TOKEN>` pelo token do bot. Procure no resultado o
campo `"chat":{"id": ...}` e guarde esse número no Secret `TELEGRAM_CHAT_ID`.
Para um grupo, adicione o bot ao grupo, envie uma mensagem no grupo e consulte
novamente `getUpdates`. Em grupos, o Chat ID costuma ser um número negativo.

O programa compara a recolha de hoje com o registo anterior do mesmo ASIN. Envia
um alerta de **Oportunidade de Vendas** quando o BSR melhora mais de 20% (o
número diminui), ou de **Queda de Preço/Guerra de Buy Box** quando o preço cai
mais de 10%.

## Instalação e execução

```bash
pip install -r requirements.txt
python main.py
```

Ao arrancar, a aplicação faz uma recolha imediata e depois executa uma recolha
todos os dias às **08:00**. Os dados são guardados em `amazon_tracker.db`.

## Dashboard

Para abrir o dashboard localmente:

```bash
streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```

O dashboard mostra a tabela completa e gráficos de evolução do BSR e do preço
por ASIN.

O workflow **Amazon Tracker + Dashboard** do Replit executa o monitor e o
Streamlit em paralelo. Se precisar de o iniciar manualmente, execute:

```bash
streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```

Depois abra a porta 8501 apresentada pelo Replit. O dashboard mostra o total
de ASINs, alertas estimados nos últimos sete dias, os dados mais recentes por
produto, gráficos interativos e um botão para descarregar todos os dados em
CSV.

O monitor disponibiliza ainda um healthcheck local em
`http://localhost:8502/health`, que responde com `{"status": "ok"}` enquanto o
processo está ativo. Ele é executado numa thread em background e não interfere
com as recolhas agendadas.

## Workflow permanente

O Workflow **Amazon Tracker + Dashboard** executa `start.sh`. Este script
funciona como supervisor: inicia `python main.py` e o Streamlit em background,
mantém ambos ativos e reinicia qualquer processo que termine. Os registos ficam
em `monitor.log` e `streamlit.log`.

O projeto encaminha a porta local `8501` para o proxy HTTPS público do Replit.
O Workflow precisa de estar ativo para o dashboard ficar disponível; fechar o
chat não substitui um Deployment ou outra opção de execução contínua do Replit.

## Descoberta automática de produtos

Todas as segundas-feiras às **07:30**, o monitor consulta o Keepa Product
Finder para a categoria definida por `KEEPA_CATEGORY_ID` na Amazon.es
(`domain=9`). São guardados apenas produtos com BSR abaixo de 20.000 e preço
entre 15 € e 50 €. Os novos ASINs ficam na tabela `monitored_products` e
entram automaticamente nas recolhas seguintes.

Opcionalmente, adicione este Secret no Replit para escolher a categoria:

```text
KEEPA_CATEGORY_ID = ID numérico da categoria Casa ou Escritório
```

Sem `KEEPA_API_KEY`, a descoberta semanal é ignorada e a aplicação continua a
monitorizar os ASINs já configurados.

## Testar o Keepa

Para verificar se a API está a responder, execute:

```bash
python main.py --test-keepa
```

Este comando indica se:

- a API do Keepa respondeu corretamente; ou
- `KEEPA_API_KEY` não está definida e estão a ser usados dados simulados.

Quando não existe a chave, o modo simulado permite testar a aplicação sem
consumir créditos nem fazer pedidos à API.