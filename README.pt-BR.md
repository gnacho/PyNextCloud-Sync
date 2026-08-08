<div align="center">
  <img src="data/icons/com.eduhcommerce.PyNextCloudSync.svg" width="112" alt="Ícone do PyNextCloud Sync">
  <h1>PyNextCloud Sync</h1>
  <p><strong>Seus arquivos, localmente. Seu Nextcloud, sincronizado.</strong></p>
  <p>Um aplicativo leve e integrado ao GNOME para manter no Linux uma cópia física completa de uma conta Nextcloud.</p>
  <p>
    <a href="README.md">English</a>
    ·
    <a href="https://eduhcommerce.com.br">Site</a>
    ·
    <a href="https://github.com/ehstbr/PyNextCloud-Sync/releases">Versões</a>
    ·
    <a href="https://github.com/ehstbr/PyNextCloud-Sync/issues">Relatar um problema</a>
  </p>
  <p>
    <img src="https://img.shields.io/badge/versão-0.1.13-6557e8?style=flat-square" alt="Versão 0.1.13">
    <img src="https://img.shields.io/badge/plataforma-Linux-f0c674?style=flat-square&logo=linux&logoColor=111" alt="Linux">
    <img src="https://img.shields.io/badge/desktop-GNOME-4a86cf?style=flat-square&logo=gnome&logoColor=white" alt="GNOME">
    <img src="https://img.shields.io/badge/GTK-4-4a86cf?style=flat-square&logo=gtk&logoColor=white" alt="GTK 4">
    <img src="https://img.shields.io/badge/licença-MIT-2da44e?style=flat-square" alt="Licença MIT">
  </p>
</div>

<p align="center">
  <img src="docs/screenshots/main-window.png" width="820" alt="Janela principal do PyNextCloud Sync durante a sincronização">
</p>

## Um aplicativo pequeno com uma função muito clara

O PyNextCloud Sync mantém **uma conta Nextcloud** espelhada em **uma pasta local**. Ele evita intencionalmente sincronização seletiva, arquivos virtuais, várias árvores de contas, painéis de métricas e recursos sem relação direta com a sincronização.

A reconciliação bidirecional é realizada pelo motor oficial [`nextcloudcmd`](https://github.com/nextcloud/desktop). O PyNextCloud Sync acrescenta a experiência de desktop: login seguro, gatilhos automáticos, janela compacta de estado, integração com o GNOME, logs e menu na bandeja.

### Destaques

- **Espelho físico completo:** todos os arquivos elegíveis da conta permanecem disponíveis localmente.
- **Motor oficial de sincronização:** sem algoritmo WebDAV próprio para reconciliar arquivos.
- **Interface nativa do GNOME:** GTK 4 e Libadwaita, com layout compacto e familiar.
- **Login seguro:** Nextcloud Login Flow v2 ou credenciais manuais armazenadas pelo Secret Service / GNOME Keyring.
- **Detecção local rápida:** monitoramento recursivo com `inotify` e agrupamento de eventos.
- **Detecção de mudanças remotas:** `notify_push` opcional com intervalo de segurança configurável.
- **Operação discreta:** uma fila que agrupa solicitações e no máximo um processo `nextcloudcmd`.
- **Integração útil com o desktop:** favorito no Arquivos, atalho na Área de Trabalho, ícone especial da pasta, inicialização automática, notificações e controles na bandeja.
- **Privacidade por princípio:** sem telemetria, analytics, publicidade ou envio remoto de falhas.
- **Multilíngue:** interface-base em inglês, com traduções para português do Brasil e espanhol.

## Capturas de tela

<table>
  <tr>
    <td width="50%" align="center"><strong>Configurações integradas ao GNOME</strong><br><img src="docs/screenshots/settings-general.png" alt="Configurações gerais"></td>
    <td width="50%" align="center"><strong>Gatilhos independentes</strong><br><img src="docs/screenshots/settings-sync.png" alt="Configurações de sincronização"></td>
  </tr>
  <tr>
    <td width="50%" align="center"><strong>Controles de rede e conta</strong><br><img src="docs/screenshots/settings-network.png" alt="Configurações de rede"></td>
    <td width="50%" align="center"><strong>Logs locais e diagnóstico</strong><br><img src="docs/screenshots/settings-advanced.png" alt="Configurações avançadas"></td>
  </tr>
</table>

<p align="center">
  <strong>As ações importantes também estão disponíveis na bandeja</strong><br><br>
  <img src="docs/screenshots/tray-menu.png" width="368" alt="Menu de bandeja do PyNextCloud Sync">
</p>

<details>
<summary><strong>Ver a configuração inicial</strong></summary>
<br>
<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/welcome.png" alt="Tela de boas-vindas"></td>
    <td width="50%"><img src="docs/screenshots/connect.png" alt="Endereço do servidor Nextcloud"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/sign-in.png" alt="Formas de entrar"></td>
    <td width="50%"><img src="docs/screenshots/browser-sign-in.png" alt="Aguardando autorização no navegador"></td>
  </tr>
  <tr>
    <td width="50%"><img src="docs/screenshots/local-folder.png" alt="Seleção da pasta local"></td>
    <td width="50%"><img src="docs/screenshots/review.png" alt="Revisão da configuração"></td>
  </tr>
</table>
</details>

## Como a sincronização funciona

Cada gatilho solicita uma reconciliação bidirecional ao mesmo agendador. Solicitações próximas são agrupadas e o aplicativo nunca inicia intencionalmente dois processos `nextcloudcmd` para a mesma conta.

```mermaid
flowchart LR
    A["Mudanças locais<br>inotify / intervalo"] --> Q["Fila única de<br>sincronização"]
    B["Sinais remotos<br>notify_push / intervalo"] --> Q
    C["Ação manual<br>rede / retomada"] --> Q
    Q --> N["nextcloudcmd"]
    N <--> F["Espelho local"]
    N <--> S["Servidor Nextcloud"]
```

O `notify_push` apenas sinaliza que pode existir uma alteração. Descoberta de arquivos, transferência, conflitos e propagação de exclusões continuam sob responsabilidade do `nextcloudcmd`.

> [!IMPORTANT]
> A sincronização é bidirecional. Alterações locais e remotas — inclusive exclusões — podem ser propagadas para o outro lado. Mantenha backup independente dos dados importantes e não execute outro sincronizador sobre a mesma pasta local.

## Instalação

### Pacote Debian — recomendado

Baixe o `.deb` na [versão mais recente](https://github.com/ehstbr/PyNextCloud-Sync/releases/latest) e instale com o APT para resolver automaticamente os pacotes de sistema necessários:

```bash
cd ~/Downloads
sudo apt update
sudo apt install ./pynextcloud-sync_0.1.13_all.deb
```

Durante uma atualização interativa iniciada com `sudo apt install`, o pacote solicita que uma instância aberta do PyNextCloud Sync seja encerrada normalmente, aguarda a sincronização atual terminar e reinicia o aplicativo atualizado na mesma sessão gráfica. O processo de sincronização nunca é encerrado à força. Atualizações automáticas ou instalações sem uma sessão gráfica identificável deixam o controle do processo para o usuário ou administrador do sistema.

O pacote depende de `nextcloud-desktop-cmd`, Python 3, GTK 4, Libadwaita, PyGObject, libsoup, libsecret, GdkPixbuf e GNOME Keyring. No GNOME, o ícone de bandeja normalmente exige uma extensão AppIndicator/StatusNotifier; a sincronização continua funcionando quando não existe um host de bandeja.

### ZIP do código-fonte

Instale primeiro as dependências:

```bash
sudo apt update
sudo apt install \
  python3 python3-gi \
  gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 \
  gir1.2-soup-3.0 gir1.2-secret-1 \
  nextcloud-desktop-cmd
```

Depois, extraia e execute:

```bash
unzip PyNextCloud-Sync-0.1.13.zip
cd PyNextCloud-Sync-0.1.13
./run.sh
```

O `run.sh` utiliza o Python e os pacotes GI da distribuição. Ele não cria ambiente virtual nem baixa pacotes da internet.

## Primeira configuração

1. Digite a URL-base usada normalmente para abrir seu Nextcloud.
2. Prefira **Entrar pelo navegador**, com suporte ao Login Flow v2 e autenticação em dois fatores. Também existe login manual com usuário e senha/senha de aplicativo.
3. Escolha a pasta do espelho local. O padrão é `$HOME/NextCloud`.
4. Revise a configuração e inicie a primeira sincronização.

Uma nova conta ativa o monitoramento local, intervalo remoto de segurança de 10 minutos, push compatível, exclusões de arquivos descartáveis e inicialização automática. O aplicativo também adiciona a pasta à lateral do Arquivos, cria um link simbólico seguro na Área de Trabalho definida pelo XDG e aplica o ícone próprio. Essas integrações podem ser alteradas separadamente em **Configurações → Geral → Pasta local**.

Se o favorito for removido pelo Arquivos, o aplicativo respeita a escolha e reflete o estado real, sem recriá-lo.

## Organização das configurações

| Área | O que controla |
| --- | --- |
| Geral | Inicialização automática, bateria, pasta local, favorito no Arquivos, atalho na Área de Trabalho e ícone especial |
| Sincronização | `inotify`, intervalo local, `notify_push`, intervalo remoto de segurança e exclusões de arquivos descartáveis |
| Rede | Remoção da conta, proxy HTTP opcional e permissão explícita para certificados inválidos ou autoassinados |
| Avançado | Logs diários, retenção, saída detalhada da sincronização e diagnóstico do runtime |

Os quatro gatilhos automáticos podem ser combinados ou desativados. Com monitoramento local, intervalo local, push e intervalo remoto desligados, o aplicativo funciona somente por sincronização manual.

## Compatibilidade

Atualmente testado com o [**Nextcloud Hub 26 Spring**](https://nextcloud.com/) **(34.0.1)** implantado pelo **Nextcloud AIO**.

A compatibilidade com outras instalações pode depender da versão do `nextcloudcmd`, configuração do servidor, proxy reverso, método de autenticação e aplicativos opcionais. Não há garantia de compatibilidade com versões futuras do Nextcloud.

## Exclusões

As regras-padrão abrangem arquivos descartáveis conservadores como `.DS_Store`, `Thumbs.db`, travas de suítes de escritório, swaps do Vim, sufixos de backup e o arquivo de ruído do diário do `nextcloudcmd`. Arquivos ocultos do usuário continuam elegíveis para sincronização porque o cliente sempre é executado com suporte a ocultos.

Padrões contendo `/`, `\` ou `..` são rejeitados. A versão 1 não permite excluir pastas, caminhos ou subárvores remotas.

## Arquivos, credenciais e privacidade

- Configuração: `$XDG_CONFIG_HOME/pynextcloud-sync/settings.json`
- Exclusões geradas: `$XDG_CONFIG_HOME/pynextcloud-sync/excludes.lst`
- Logs diários: `$XDG_STATE_HOME/pynextcloud-sync/pynextcloud-sync-YYYY-MM-DD.log`
- Segredo da conta: GNOME Keyring ou outro provedor compatível com Secret Service

Os logs permanecem no computador, usam um arquivo por dia e são mantidos por 30 dias por padrão. Valores sensíveis são ocultados das mensagens de log geradas pelo aplicativo. Se o login biométrico deixar a carteira `Login` bloqueada, o GNOME exibe sua solicitação nativa de desbloqueio antes da sincronização. A senha do computador é tratada somente pelo GNOME; o PyNextCloud Sync não a recebe nem armazena. Cancelar a solicitação deixa o aplicativo aguardando o comando explícito **Desbloquear carteira de senhas**, sem repetir diálogos ou acusar credenciais inválidas do Nextcloud.

## Desenvolvimento e testes

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

A suíte em Python puro inclui um `nextcloudcmd` simulado para cenários de sucesso, falha, erro de autenticação, saída e execução lenta. Testes com conta real, host de bandeja do GNOME, UPower, suspensão/retomada e memória de longa duração ainda exigem uma sessão desktop real.

Contribuições são bem-vindas quando preservam o escopo enxuto, baixo consumo ocioso, tratamento seguro de credenciais e design orientado ao GNOME. Consulte [CONTRIBUTING.md](CONTRIBUTING.md).

## Documentação

- [Histórico de alterações](CHANGELOG.md)
- [Termos de Uso em português](TERMS.pt-BR.md)
- [Licença MIT](LICENSE)
- [Projetos de terceiros e licenças](THIRD-PARTY.pt-BR.md)
- [Como contribuir](CONTRIBUTING.md)

## Estado do projeto

A versão `0.1.13` é uma versão de desenvolvimento destinada à avaliação. Teste primeiro com dados não críticos e mantenha sempre backups independentes dos arquivos importantes.

---

<p align="center"><sub>
Nextcloud® é marca registrada da Nextcloud GmbH. O PyNextCloud Sync é um projeto independente e não oficial, sem afiliação, patrocínio, endosso ou qualquer outro vínculo com a Nextcloud GmbH. O uso está sujeito aos <a href="TERMS.pt-BR.md">Termos de Uso</a> e à Licença MIT.
</sub></p>
