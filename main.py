import os
from flask import Flask, render_template, request, flash, redirect, send_file, url_for, session, send_from_directory
from flask_bcrypt import generate_password_hash, check_password_hash
from datetime import datetime, date, timedelta
from validate_docbr import CPF
import psycopg2
from fpdf import FPDF
import pygal

app = Flask(__name__)

host = 'localhost'
database = r'C:\Users\Aluno\Desktop\AURO2.FDB'
user = 'sysdba'
password = 'sysdba'

app.secret_key = 'Auro2025'

con = psycopg2.connect(
    os.environ["DATABASE_URL"]
)

def validaCpf(usercpf):
    cpf = CPF()
    return cpf.validate(usercpf)

def atualizaHistorico(id_usuario, mes, ano):
    cursor = con.cursor()
    try:

        #     condição   tipo
        # 0 = despesa e fixa
        # 1 = receita e variavel

        # pega as movimentações fixas
        cursor.execute("""
            SELECT VALOR, DATA_ATUAL, CONDICAO, ID_MOVIMENTACAO, DESCRICAO
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND TIPO = 0 AND EXTRACT(YEAR FROM DATA_ATUAL) = ? AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
            ORDER BY DATA_ATUAL ASC
        """, (id_usuario, ano, mes,))
        fixas = cursor.fetchall()

        # pega as movimentações variaveis do mês selecionado
        cursor.execute("""
            SELECT VALOR, DATA_ATUAL, CONDICAO, ID_MOVIMENTACAO, DESCRICAO
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND EXTRACT(MONTH FROM DATA_ATUAL) = ? AND TIPO = 1
            ORDER BY DATA_ATUAL ASC
        """, (id_usuario, mes,))
        movimentacoes = cursor.fetchall()

        # pega as parcelas em movimentacao
        cursor.execute("""
            SELECT VALOR, DATA_ATUAL, CONDICAO, ID_MOVIMENTACAO, DESCRICAO
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND TIPO = 2 AND EXTRACT(MONTH FROM DATA_ATUAL) = ? AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            ORDER BY DATA_ATUAL ASC
        """, (id_usuario, mes, ano,))
        parcelas = cursor.fetchall()

        # pega as movimetações que são parcelas dos emprestiomos do mes selecionado
        # cursor.execute("""
        #     SELECT VALOR_PARCELA, DATA_VENCIMENTO, 0 AS CONDICAO, ep.ID_EMPRESTIMO AS ID_MOVIMENTACAO, 'Parcela Empréstimo' AS DESCRICAO
        #     FROM EMPRESTIMO_PARCELA ep
        #     WHERE ep.ID_EMPRESTIMO IN (
        #         SELECT ID_EMPRESTIMO
        #         FROM EMPRESTIMO
        #         WHERE ID_USUARIO = ? AND EXTRACT(YEAR FROM DATA_EMPRESTIMO) = ? AND EXTRACT(MONTH FROM DATA_EMPRESTIMO) = ?
        #     )
        # """, (id_usuario, ano, mes,))
        # parcelas = cursor.fetchall()

        # pega o valor das receitas variaveis do mês selecionado
        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1 AND EXTRACT(YEAR FROM DATA_ATUAL) = ? AND EXTRACT(MONTH FROM DATA_ATUAL) = ? AND TIPO = 1
        """, (id_usuario, ano, mes,))
        receitas_variaveis = cursor.fetchone()[0] or 0

        # pega o valor das receitas fixas
        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1 AND TIPO = 0 AND EXTRACT(YEAR FROM DATA_ATUAL) = ? AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
        """, (id_usuario, ano, mes,))
        receitas_fixas = cursor.fetchone()[0] or 0

        # pega o valor do emprestimo do mês selecionado
        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND EXTRACT(YEAR FROM DATA_ATUAL) = ? AND EXTRACT(MONTH FROM DATA_ATUAL) = ? AND TIPO = 2 AND CONDICAO = 1
        """, (id_usuario, ano, mes,))
        emprestimos = cursor.fetchone()[0] or 0

        # pega o valor das despesas variaveis do mês selecionado
        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0 AND TIPO = 1 AND EXTRACT(YEAR FROM DATA_ATUAL) = ? AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
        """, (id_usuario, ano, mes,))
        despesas_variaveis = cursor.fetchone()[0] or 0

        # pega o valor das despesas fixas
        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0 AND TIPO = 0 AND EXTRACT(YEAR FROM DATA_ATUAL) = ? AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
        """, (id_usuario, ano, mes,))
        despesas_fixas = cursor.fetchone()[0] or 0

        # pega o valor das parcelas dos emprestimos
        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND EXTRACT(YEAR FROM DATA_ATUAL) = ? AND EXTRACT(MONTH FROM DATA_ATUAL) = ? AND TIPO = 2 AND CONDICAO = 0
        """, (id_usuario, ano, mes,))
        parcelas_emprestimos = cursor.fetchone()[0] or 0

        receita = receitas_variaveis + receitas_fixas + emprestimos
        despesa = despesas_variaveis + despesas_fixas + parcelas_emprestimos
        saldo = receita - despesa
    finally:
        cursor.close()

    infos = {
        "movimentacoes": movimentacoes,
        "saldo": saldo,
        "receita": receita,
        "despesa": despesa,
        "fixas": fixas,
        "parcelas": parcelas
    }

    return infos
    

@app.route('/')
def index():  # def é um função
    usuario = session.get('usuario_logado')  # pega o usuario logado
    cpf = session.get('cpf_usuario')  # pega o cpf do usuario
    tipo_usuario = session.get('tipo_usuario')  # pega o tipo do usuario
    e_admin = (tipo_usuario == 1)  # se o tipo do usuario for 1 é admin
    e_usuario = (tipo_usuario == 0)  # se o tipo do usuario for 0 é usuario comum
    return render_template('index.html', usuario=usuario, e_admin=e_admin, e_usuario=e_usuario, cpf=cpf)


@app.route('/abrir_login')
def abrir_login():
    if session.get('usuario_logado'):  # session.get se o usuario estiver logado
        if session.get('tipo_usuario') == 0:  # usuario 0 e o admin 1
            return redirect(url_for('perfil_cliente'))
        return redirect(url_for('perfil_admin'))
    return render_template('login.html')


@app.route('/abrir_cadastro')
def abrir_cadastro():
    if session.get('usuario_logado'):
        flash('Deslogue antes de criar um novo cadastro.', 'erro')
        return redirect(url_for('index'))
    return render_template('cadastro.html')


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if session.get('usuario_logado'):  # se o usuario estiver logado.
        flash('Deslogue antes de criar um novo cadastro.', 'erro')  # deslogue antes de criar um novo cadastro
        return redirect(url_for('index'))

    etapa = request.form['etapa']

    if etapa == '1':
        nome = request.form['nome']  # pega o nome do formulario
        cpf = request.form['cpf']  # pega o cpf do formulario

        if validaCpf(cpf) == False:
            flash('CPF inválido, informe um CPF existente!', 'erro')
            return redirect(url_for('abrir_cadastro'))
        data_nasc_str = request.form['dataNascimento']
        nascimento = datetime.strptime(data_nasc_str, '%Y-%m-%d').date()
        hoje = date.today()
        idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
        if idade < 18:
            flash('Você precisa ter pelo menos 18 anos para se cadastrar.', 'erro')
            return redirect(url_for('abrir_cadastro'))
        cursor = con.cursor()
        try:
            cursor.execute("SELECT 1 FROM USUARIO WHERE CPF = ?", (cpf,))
            if cursor.fetchone():
                flash('CPF já cadastrado.', 'erro')
                return render_template('cadastro.html', etapa=1)

            session['foto_temp'] = f"{cpf[:4]}"
        finally:
            cursor.close()
        session['nome'] = nome
        session['cpf'] = cpf
        session['dataNascimento'] = data_nasc_str
        return render_template('cadastro.html', etapa=2)
    elif etapa == '2':
        email = request.form['email']
        cripyt_senha = request.form['senha']
        cursor = con.cursor()
        try:
            cursor.execute("SELECT 1 FROM USUARIO WHERE EMAIL = ?", (email,))
            if cursor.fetchone():
                flash('E-mail já cadastrado.', 'erro')
                return render_template('cadastro.html', etapa=2)
            arquivo = request.files['arquivo']
            if arquivo and arquivo.filename:
                # Verificar extensão do arquivo
                filename = arquivo.filename
                # Pegar a extensão do arquivo em minúsculas
                extensao = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                session['extensao'] = extensao

                # Verificar se a extensão é permitida
                if extensao not in ['png', 'jpg', 'jpeg', 'gif']:
                    flash('Tipo de arquivo não permitido. Use apenas PNG, JPG, JPEG ou GIF.', 'erro')
                    return render_template('cadastro.html', etapa=2)

                arquivo.save(f'static/uploads/{session["foto_temp"]}.{extensao}')
            else:
                session['extensao'] = ''


        finally:
            cursor.close()
        session['email'] = email
        session['senha'] = generate_password_hash(cripyt_senha).decode('utf-8')
        return render_template('cadastro.html', etapa=3)
    elif etapa == '3':
        confirmaEmail = request.form['confirmaEmail']
        confirmaCpf = request.form['confirmaCpf']
        if validaCpf(confirmaCpf) == False:
            flash('CPF inválido!', 'erro')
            return redirect(url_for('abrir_cadastro'))
        confirmaNome = request.form['confirmaNome']
        confirmaDataNascimento = request.form['confirmaDataNascimento']
        nascimento = datetime.strptime(confirmaDataNascimento, '%Y-%m-%d').date()
        hoje = date.today()
        idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
        if idade < 18:
            flash('Você precisa ter pelo menos 18 anos para se cadastrar.', 'erro')
            return render_template('cadastro.html', etapa=3)
        cursor = con.cursor()
        try:
            if confirmaCpf != session['cpf']:
                cursor.execute("SELECT 1 FROM USUARIO WHERE CPF = ?", (confirmaCpf,))
                if cursor.fetchone():
                    flash('CPF já cadastrado.', 'erro')
                    return render_template('cadastro.html', etapa=3)
            if confirmaEmail != session['email']:
                cursor.execute("SELECT 1 FROM USUARIO WHERE EMAIL = ?", (confirmaEmail,))
                if cursor.fetchone():
                    flash('E-mail já cadastrado.', 'erro')
                    return render_template('cadastro.html', etapa=3)
        except:
            flash('Erro ao verificar dados.', 'erro')
            return redirect(url_for('abrir_cadastro'))
        finally:
            cursor.close()
        if confirmaNome != session['nome']:
            session['nome'] = confirmaNome
        if confirmaEmail != session['email']:
            session['email'] = confirmaEmail
        if confirmaCpf != session['cpf']:
            session['cpf'] = confirmaCpf
        if confirmaDataNascimento != session['dataNascimento']:
            session['dataNascimento'] = confirmaDataNascimento
        cursor = con.cursor()
        try:
            cursor.execute("""
                           INSERT INTO USUARIO (NOME, EMAIL, SENHA, CPF, SITUACAO, TIPO, TENTATIVA, DATA_NASCIMENTO)
                           VALUES (?, ?, ?, ?, 0, 0, 0, ?)
                           """, (
                session['nome'],
                session['email'],
                session['senha'],
                session['cpf'],
                session['dataNascimento']
            ))
            con.commit()
            cursor.execute("SELECT ID_USUARIO FROM USUARIO WHERE CPF = ?", (session['cpf'],))
            id_usuario = cursor.fetchone()[0]

            if session["extensao"]:
                os.rename(f'static/uploads/{session["foto_temp"]}.{session["extensao"]}',
                          f'static/uploads/{id_usuario}.{session["extensao"]}')
                session.pop('foto_temp')  # Limpar sessão
                session.pop('extensao')  # Limpar sessão

            flash("Cadastro realizado com sucesso!", 'sucesso')
            return redirect(url_for('abrir_login'))
        finally:
            cursor.close()


@app.route('/login', methods=['POST'])
def login():
    cpf = request.form['cpf']
    senha = request.form['senha']
    valido = False
    cursor = con.cursor()
    try:
        cursor.execute("SELECT NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        resultado = cursor.fetchone()
        if not resultado:
            flash('CPF não encontrado.', 'erro')
            return redirect(url_for('abrir_login'))
        nome = resultado[0]

        cursor.execute("SELECT SITUACAO, SENHA, TIPO, TENTATIVA, ID_USUARIO FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('abrir_login'))
        situacao, senha_hash, tipo, tentativas, id_usuario = usuario

        if situacao == 1:
            flash('Conta inativa. Entre em contato com o suporte.', 'erro')
            return redirect(url_for('abrir_login'))

        if tipo == 1:
            if senha == senha_hash:
                valido = True
        else:
            if check_password_hash(senha_hash, senha):
                valido = True

        if valido:
            cursor.execute("UPDATE USUARIO SET TENTATIVA = 0 WHERE CPF = ?", (cpf,))
            con.commit()

            extensoes_permitidas = ['png', 'jpg', 'jpeg', 'gif']
            extensao_imagem = ''

            for extensao in extensoes_permitidas:
                caminho_imagem = f'static/uploads/{id_usuario}.{extensao}'
                if os.path.exists(caminho_imagem):
                    extensao_imagem = extensao
                    break
            # Armazenar dados na sessão, incluindo id_usuario
            session['usuario_logado'] = True
            session['nome_usuario'] = nome
            session['cpf_usuario'] = cpf
            session['tipo_usuario'] = tipo
            session['senha_usuario'] = senha
            session['id_usuario'] = id_usuario
            session['extensao_imagem'] = extensao_imagem
            flash('Login realizado com sucesso!', 'sucesso')
            if tipo == 1:
                return redirect(url_for('perfil_admin'))
            else:
                return redirect(url_for('perfil_cliente'))
        else:
            if tipo == 1:
                flash('Senha incorreta.', 'erro')
                return redirect(url_for('abrir_login'))
            novas = tentativas + 1
            if novas >= 3:
                cursor.execute("""
                    UPDATE USUARIO
                    SET TENTATIVA = ?, SITUACAO = 1
                    WHERE CPF = ?
                """, (novas, cpf))
                flash('Conta bloqueada após 3 tentativas. Entre em contato com o suporte.', 'erro')
            else:
                cursor.execute("UPDATE USUARIO SET TENTATIVA = ? WHERE CPF = ?", (novas, cpf))
                flash('Senha incorreta.', 'erro')
            con.commit()
            return redirect(url_for('abrir_login'))
    finally:
        cursor.close()


@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'sucesso')
    return redirect(url_for('index'))


@app.route('/perfil_admin')
def perfil_admin():
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Somente administradores podem acessar esta página.', 'erro')
        return redirect(url_for('index'))
    session.pop('visualizar_usuario_cpf', None)  # Limpar CPF de visualização anterior, se existir
    cursor = con.cursor()
    try:
        cursor.execute("SELECT NOME, CPF, ID_USUARIO FROM USUARIO WHERE TIPO=0")
        usuarios = cursor.fetchall()
        cursor.execute("SELECT NOME, CPF, ID_USUARIO FROM USUARIO WHERE TIPO=1")
        adms = cursor.fetchall()

        # Buscar taxas ordenadas por data
        cursor.execute("""
                       SELECT ID_TAXA, DESCRICAO, VALOR, DATA_INICIO, DATA_FINAL
                       FROM TAXA
                       ORDER BY DATA_INICIO, ID_TAXA DESC
                       """)
        taxas = cursor.fetchall()

        # Buscar extensões das imagens para todos os usuários
        extensoes_usuarios = {}
        extensoes_permitidas = ['png', 'jpg', 'jpeg', 'gif']

        # Para usuários comuns
        for usuario in usuarios:
            id_usuario = usuario[2]
            for extensao in extensoes_permitidas:
                caminho_imagem = f'static/uploads/{id_usuario}.{extensao}'
                if os.path.exists(caminho_imagem):
                    extensoes_usuarios[id_usuario] = extensao
                    break
            # Se não encontrou imagem, define como vazio
            if id_usuario not in extensoes_usuarios:
                extensoes_usuarios[id_usuario] = ''

        # Para administradores
        for adm in adms:
            id_adm = adm[2]
            for extensao in extensoes_permitidas:
                caminho_imagem = f'static/uploads/{id_adm}.{extensao}'
                if os.path.exists(caminho_imagem):
                    extensoes_usuarios[id_adm] = extensao
                    break
            # Se não encontrou imagem, define como vazio
            if id_adm not in extensoes_usuarios:
                extensoes_usuarios[id_adm] = ''

    finally:
        cursor.close()

    return render_template('perfil_adm.html',
                           usuarios=usuarios,
                           adms=adms,
                           taxas=taxas,
                           extensoes_usuarios=extensoes_usuarios)


@app.route('/perfil_cliente')
def perfil_cliente():
    if not session.get('usuario_logado'):
        flash('Você precisa estar logado para acessar o perfil.', 'erro')
        return redirect(url_for('abrir_login'))

    tipo_usuario = session.get('tipo_usuario')
    if tipo_usuario == 1:  # se for admin
        return redirect(url_for('perfil_admin'))

    cpf = session['cpf_usuario']
    nome = session['nome_usuario']
    id_usuario = session.get('id_usuario')

    cursor = con.cursor()
    try:
        cursor.execute("SELECT DATA_NASCIMENTO FROM USUARIO WHERE CPF = ?", (cpf,))
        user = cursor.fetchone()
        data_nascimento = user[0]

        # Buscar total de receitas
        cursor.execute("""
                       SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND CONDICAO = 1
                       """, (id_usuario,))
        total_receitas = cursor.fetchone()[0] or 0

        # Buscar total de despesas
        cursor.execute("""
                       SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND CONDICAO = 0
                       """, (id_usuario,))
        total_despesas = cursor.fetchone()[0] or 0

        # Calcular saldo
        saldo = total_receitas - total_despesas

        return render_template('perfil.html',
                               nome_usuario=nome,
                               data_nascimento=data_nascimento,
                               cpf=cpf,
                               saldo=saldo)
    finally:
        cursor.close()


@app.route('/editar_usuario/<cpf>', methods=['GET', 'POST'])
def editar_usuario(cpf):
    if not session.get('usuario_logado'):
        flash('Você precisa estar logado para editar o perfil.', 'erro')
        return redirect(url_for('abrir_login'))

    tipo_usuario = session.get('tipo_usuario')
    e_admin = (tipo_usuario == 1)

    if tipo_usuario != 1:
        cpf = session['cpf_usuario']

    cursor = con.cursor()
    try:
        if request.method == 'POST':
            nome_novo = request.form['nome']
            cpf_novo = request.form['cpf']
            if validaCpf(cpf_novo) == False:
                flash('CPF inválido!', 'erro')
                return redirect(url_for('editar_usuario', cpf=cpf))
            senha_form = request.form.get('senha', '')
            email_novo = request.form['email']
            data_novo = request.form['data_nascimento']

            nasc = datetime.strptime(data_novo, '%Y-%m-%d').date()
            hoje = date.today()
            idade = hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
            if idade < 18:
                flash('É preciso ter mais de 18 anos.', 'erro')
                return redirect(url_for('editar_usuario', cpf=cpf))

            if cpf_novo != cpf:
                cursor.execute("SELECT 1 FROM USUARIO WHERE CPF = ?", (cpf_novo,))
                if cursor.fetchone():
                    flash('CPF já cadastrado.', 'erro')
                    return redirect(url_for('editar_usuario', cpf=cpf))

            cursor.execute("SELECT EMAIL FROM USUARIO WHERE CPF = ?", (cpf,))
            email_atual = cursor.fetchone()[0]
            if email_novo != email_atual:
                cursor.execute("SELECT 1 FROM USUARIO WHERE EMAIL = ?", (email_novo,))
                if cursor.fetchone():
                    flash('Email já cadastrado.', 'erro')
                    return redirect(url_for('editar_usuario', cpf=cpf))

            if senha_form.strip():
                if not e_admin:
                    nova_hash = generate_password_hash(senha_form).decode('utf-8')
                    session['senha_usuario'] = senha_form
                else:
                    cursor.execute("SELECT SENHA FROM USUARIO WHERE CPF = ?", (cpf,))
                    nova_hash = cursor.fetchone()[0]
            else:
                cursor.execute("SELECT SENHA FROM USUARIO WHERE CPF = ?", (cpf,))
                nova_hash = cursor.fetchone()[0]

            if e_admin:
                cursor.execute("SELECT ID_USUARIO FROM USUARIO WHERE CPF = ?", (cpf_novo,))
                id_usuario = cursor.fetchone()[0]
                arquivo = request.files.get('arquivo')
                if arquivo and arquivo.filename:
                    # Verificar extensão do arquivo
                    filename = arquivo.filename
                    extensao = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
                    extensoes_permitidas = ['png', 'jpg', 'jpeg', 'gif']
                    for ext in extensoes_permitidas:
                        caminho_antigo = f'static/uploads/{id_usuario}.{ext}'
                        if os.path.exists(caminho_antigo):
                            os.remove(caminho_antigo)
                        # Salvar nova imagem
                    nome_arquivo = f"{id_usuario}"
                    arquivo.save(f'static/uploads/{nome_arquivo}.{extensao}')
                situacao_nova = int(request.form.get('situacao', 1))
                cursor.execute("SELECT SITUACAO, TENTATIVA FROM USUARIO WHERE CPF = ?", (cpf,))
                situacao_atual, tentativas_atual = cursor.fetchone()
                if situacao_atual == 1 and situacao_nova == 0:
                    tentativas_nova = 0
                else:
                    tentativas_nova = tentativas_atual
            else:
                cursor.execute("SELECT SITUACAO, TENTATIVA FROM USUARIO WHERE CPF = ?", (cpf,))
                situacao_nova, tentativas_nova = cursor.fetchone()

                arquivo = request.files.get('arquivo')
                extensoes_permitidas = ['png', 'jpg', 'jpeg', 'gif']

                if arquivo and arquivo.filename:
                    # Verificar extensão do arquivo
                    filename = arquivo.filename
                    extensao = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

                    for ext in extensoes_permitidas:
                        caminho_antigo = f'static/uploads/{session['id_usuario']}.{ext}'
                        if os.path.exists(caminho_antigo):
                            os.remove(caminho_antigo)

                        # Salvar nova imagem
                    nome_arquivo = f"{session['id_usuario']}"
                    arquivo.save(f'static/uploads/{nome_arquivo}.{extensao}')

                    # Atualizar extensão na sessão se for o próprio usuário editando
                    if tipo_usuario == 0:
                        session['extensao_imagem'] = extensao

            cursor.execute("""
                           UPDATE USUARIO
                           SET NOME            = ?,
                               CPF             = ?,
                               SENHA           = ?,
                               EMAIL           = ?,
                               DATA_NASCIMENTO = ?,
                               SITUACAO        = ?,
                               TENTATIVA       = ?
                           WHERE CPF = ?
                           """,
                           (nome_novo, cpf_novo, nova_hash, email_novo, data_novo, situacao_nova, tentativas_nova, cpf))
            con.commit()

            if tipo_usuario == 0:
                session['nome_usuario'] = nome_novo
                session['cpf_usuario'] = cpf_novo

            flash('Perfil atualizado com sucesso!', 'sucesso')
            if tipo_usuario == 1:
                return redirect(url_for('visualizar_usuario', cpf=cpf_novo))
            else:
                return redirect(url_for('perfil_cliente'))
        else:
            cursor.execute("""
                           SELECT NOME, CPF, SENHA, EMAIL, DATA_NASCIMENTO, SITUACAO
                           FROM USUARIO
                           WHERE CPF = ?
                           """, (cpf,))
            usuario = cursor.fetchone()
            if not usuario:
                flash('Usuário não encontrado.', 'erro')
                return redirect(url_for('index'))
            nome = usuario[0]
            cpf_form = usuario[1]
            senha_texto = session.get('senha_usuario', '') if tipo_usuario == 0 else ''
            email = usuario[3]
            data_nascimento = usuario[4]
            situacao = usuario[5]
            return render_template('editar_usuario.html', nome=nome, cpf=cpf_form,
                                   senha=senha_texto, email=email, data_nascimento=data_nascimento,
                                   situacao=situacao, e_admin=e_admin)
    finally:
        cursor.close()


@app.route('/admin/usuario/<cpf>')
def visualizar_usuario(cpf):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito.', 'erro')
        return redirect(url_for('index'))
    cursor = con.cursor()
    try:
        cursor.execute("SELECT NOME, CPF, EMAIL, DATA_NASCIMENTO, ID_USUARIO FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        session['visualizar_usuario_cpf'] = cpf
    finally:
        cursor.close()
    return render_template('perfil.html',
                           nome_usuario=usuario[0],
                           cpf=usuario[1],
                           email=usuario[2],
                           data_nascimento=usuario[3],
                           id_usuario=usuario[4])


@app.route('/visualizar_adm')
def visualizar_adm():
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))
    return render_template('cadastrar_adm.html')


@app.route('/admin/cadastrar_adm', methods=['POST'])
def cadastrar_adm():
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso negado: somente administradores podem cadastrar outros administradores.', 'erro')
        return redirect(url_for('index'))
    nome = request.form.get('nome')
    cpf = request.form.get('cpf')
    email = request.form.get('email')
    senha = request.form.get('senha')

    cursor = con.cursor()
    try:
        cursor.execute("SELECT 1 FROM USUARIO WHERE CPF = ?", (cpf,))
        if cursor.fetchone():
            flash('CPF já cadastrado.', 'erro')
            return redirect(url_for('visualizar_adm'))

        cursor.execute("SELECT 1 FROM USUARIO WHERE EMAIL = ?", (email,))
        if cursor.fetchone():
            flash('E-mail já cadastrado.', 'erro')
            return redirect(url_for('visualizar_adm'))

        cursor.execute("""
            INSERT INTO USUARIO (NOME, EMAIL, SENHA, CPF, SITUACAO, TIPO, TENTATIVA, DATA_NASCIMENTO)
            VALUES (?, ?, ?, ?, 0, 1, 0, ?)
        """, (
            nome,
            email,
            senha,
            cpf,
            '2000-01-01'
        ))
        con.commit()
        flash('Administrador cadastrado com sucesso!', 'sucesso')
        return redirect(url_for('perfil_admin'))
    finally:
        cursor.close()


@app.route('/dashboard')
def dashboard():
    if not session.get('usuario_logado'):
        flash('Faça login para acessar o dashboard.', 'erro')
        return redirect(url_for('abrir_login'))
    if session.get('tipo_usuario') == 1:
        flash('Administradores não têm dashboard.', 'erro')
        return redirect(url_for('perfil_admin'))
    id_usuario = session.get('id_usuario')
    cursor = con.cursor()

    try:
        # [CORREÇÃO 1] Garante que a transação esteja limpa
        # para ler os dados mais recentes (corrige o problema de dados zerados)
        con.rollback()

        # Ano selecionado ou atual
        ano_selecionado = request.args.get('ano', datetime.now().year, type=int)

        # Dados totais
        cursor.execute("""
                       SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND CONDICAO = 1
                       """, (id_usuario,))
        total_receitas = cursor.fetchone()[0] or 0

        cursor.execute("""
                       SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND CONDICAO = 0
                       """, (id_usuario,))
        total_despesas = cursor.fetchone()[0] or 0

        saldo = total_receitas - total_despesas

        # Verificar se existem movimentações no ano selecionado
        # (Sua lógica original usava DATA_ATUAL, mantive isso)
        cursor.execute("""
                       SELECT COUNT(*)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
                       """, (id_usuario, ano_selecionado))
        tem_movimentacoes_ano = cursor.fetchone()[0] > 0

        # Dados mensais para o gráfico de barras
        receitas_mensais = [0.0] * 12
        despesas_mensais = [0.0] * 12
        meses_nomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                       'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

        # Buscar receitas (variáveis + fixas)
        for mes in range(1, 13):
            # Receitas variáveis do mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 1
                AND TIPO = 1
                AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            receitas_variaveis = float(cursor.fetchone()[0])

            # Receitas fixas acumuladas até este mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 1
                AND TIPO = 0
                AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            receitas_fixas = float(cursor.fetchone()[0])

            # emprestimo na tabela movimentacao tipo 2 e condição 1
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND TIPO = 2
                AND CONDICAO = 1
                AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            emprestimos = float(cursor.fetchone()[0])

            receitas_mensais[mes - 1] = receitas_variaveis + receitas_fixas + emprestimos

        # Buscar despesas (variáveis + fixas)
        for mes in range(1, 13):
            # Despesas variáveis do mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 0
                AND TIPO = 1
                AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            despesas_variaveis = float(cursor.fetchone()[0])

            # Despesas fixas acumuladas até este mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 0
                AND TIPO = 0
                AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            despesas_fixas = float(cursor.fetchone()[0])

            # Parcelas de empréstimos na tabela movimentacao tipo 2 e condição 0
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND TIPO = 2
                AND CONDICAO = 0
                AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            parcelas_emprestimos = float(cursor.fetchone()[0])

            despesas_mensais[mes - 1] = despesas_variaveis + despesas_fixas + parcelas_emprestimos

        # Criar gráfico de barras com Pygal - SEMPRE gerar se houver movimentações no ano
        grafico_svg = None

        if tem_movimentacoes_ano:
            # Configuração do gráfico
            bar_chart = pygal.Bar(
                height=400,
                width=800,
                explicit_size=True,
                title=f'Receitas e Despesas - {ano_selecionado}',
                x_title='Meses',
                y_title='Valor (R$)',
                show_legend=True,
                print_values=False,
                # [CORREÇÃO 2] Corrigido de 'pygal.styles' para 'pygal.style'
                style=pygal.style.DefaultStyle(
                    colors=('#28a745', '#dc3545'),  # Verde para receitas, vermelho para despesas
                    background=('transparent')
                )
            )

            # Definir labels dos meses
            bar_chart.x_labels = meses_nomes

            # Adicionar as barras
            bar_chart.add('Receitas', receitas_mensais)
            bar_chart.add('Despesas', despesas_mensais)

            # Renderizar como SVG
            grafico_svg = bar_chart.render(is_unicode=True)

    except:
        flash(f'Erro ao gerar gráfico', 'erro')
        grafico_svg = None
        # (Mantive sua lógica de erro)
        receitas_mensais = []
        despesas_mensais = []
    finally:
        cursor.close()

    return render_template('dashboard.html',
                           total_receitas=total_receitas,
                           total_despesas=total_despesas,
                           saldo=saldo,
                           ano_selecionado=ano_selecionado,
                           grafico_svg=grafico_svg,
                           tem_movimentacoes_ano=tem_movimentacoes_ano)


@app.route('/dashboard_simulacao')
def dashboard_simulacao():
    if not session.get('usuario_logado'):
        flash('Faça login para acessar a simulação.', 'erro')
        return redirect(url_for('abrir_login'))
    if session.get('tipo_usuario') == 1:
        flash('Administradores não têm dashboard.', 'erro')
        return redirect(url_for('perfil_admin'))
    data_nf = datetime.now().strftime('%Y-%m-%d')
    data = datetime.strptime(data_nf, '%Y-%m-%d').date()
    return render_template('dashboard_simulacao.html', data=data)


@app.route('/dashboard_simulacao_analise', methods=['POST'])
def dashboard_simulacao_analise():
    if not session.get('usuario_logado'):
        flash('Faça login para acessar a simulação.', 'erro')
        return redirect(url_for('abrir_login'))
    if session.get('tipo_usuario') == 1:
        flash('Administradores não têm dashboard.', 'erro')
        return redirect(url_for('perfil_admin'))
    id_usuario = session.get('id_usuario')
    etapa = 2
    cursor = con.cursor()
    mes = datetime.now().month
    valor = float(request.form['valor'])
    parcelas = int(request.form['parcelas'])
    data_nf = datetime.now().strftime('%Y-%m-%d')
    data = datetime.strptime(data_nf, '%Y-%m-%d').date()
    try:
        cursor.execute("""
            SELECT VALOR FROM TAXA WHERE DATA_FINAL IS NULL
        """)
        taxa = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1 AND TIPO = 1 AND EXTRACT(MONTH FROM DATA_ATUAL) = ?    
        """, (id_usuario, mes,))
        total_receitas = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0 AND TIPO = 1 AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
        """, (id_usuario, mes,))
        total_despesas = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1 AND TIPO = 0 AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?    
        """, (id_usuario, mes,))
        total_receitas += cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0 AND TIPO = 0 AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
        """, (id_usuario, mes,))
        total_despesas += cursor.fetchone()[0] or 0

        saldo = float(total_receitas) - float(total_despesas)

        if taxa > 0:
            pmt = valor * (float(taxa) / 100) / (1 - (1 + float(taxa) / 100) ** -parcelas)
        else:
            pmt = valor / parcelas

        if saldo <= 0:
            comprometimento = 100
        else:
            comprometimento = (pmt / saldo) * 100
        if comprometimento <= 20:
            risco = 'Baixo'
        elif 20 < comprometimento <= 35:
            risco = 'Médio'
        else:
            risco = 'Alto'
        valor_total = round(pmt * parcelas, 2)
    finally:
        cursor.close()
    return render_template('dashboard_simulacao.html', etapa=etapa, comprometimento=round(comprometimento, 2),
                           pmt=round(pmt, 2), parcelas=parcelas, risco=risco, valor_total=float(valor_total),
                           valor=valor, data=data)


@app.route('/confirmar_emprestimo', methods=['POST'])
def confirmar_emprestimo():
    if not session.get('usuario_logado'):
        flash('Faça login para confirmar o empréstimo.', 'erro')
        return redirect(url_for('abrir_login'))
    if session.get('tipo_usuario') == 1:
        flash('Administradores não têm dashboard.', 'erro')
        return redirect(url_for('perfil_admin'))
    cursor = con.cursor()
    try:
        valor = float(request.form.get('valor'))
        parcelas = int(request.form.get('parcelas'))
        valor_total = float(request.form.get('valor_total'))
        pmt = float(request.form.get('pmt'))
        data = datetime.now().strftime('%Y-%m-%d')
        data_empr = datetime.strptime(data, '%Y-%m-%d').date()
        cursor.execute("""
            SELECT ID_TAXA FROM TAXA WHERE DATA_FINAL IS NULL
        """)
        id_taxa = cursor.fetchone()[0]
        cursor.execute("""
            INSERT INTO EMPRESTIMO (VALOR_TOTAL, QTD_PARCELA, SITUACAO, DATA_EMPRESTIMO, ID_USUARIO, ID_TAXA, VALOR_ORIGINAL)
            VALUES (?, ?, 0, ?, ?, ?, ?)""",
                       (valor_total, parcelas, data_empr, session.get('id_usuario'), id_taxa, valor))
        con.commit()

        cursor.execute("""
            SELECT MAX(ID_EMPRESTIMO) FROM EMPRESTIMO WHERE ID_USUARIO = ?
        """, (session.get('id_usuario'),))
        id_emprestimo = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, DATA_ATUAL, CONDICAO, TIPO, ID_USUARIO)
            VALUES (?, ?, ?, 1, 2, ?)
            """, (f'Empréstimo', valor, data_empr, session.get('id_usuario')))
        con.commit()

        con.commit()

        for i in range(1, parcelas + 1):
            data_com_dia_7 = data_empr.replace(day=7)
            data_empr = data_com_dia_7
            data_empr += timedelta(days=30)
            data_com_dia_7 = data_empr.replace(day=7)
            data_empr = data_com_dia_7
            cursor.execute("""
                INSERT INTO EMPRESTIMO_PARCELA (ID_EMPRESTIMO, VALOR_PARCELA, DATA_VENCIMENTO, SEQUENCIA_PARCELA)
                VALUES (?, ?, ?, ?)
                """, (id_emprestimo, pmt, data_empr, i))
            cursor.execute("""
            INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, DATA_ATUAL, CONDICAO, TIPO, ID_USUARIO)
            VALUES (?, ?, ?, 0, 2, ?)
            """, (f'Empréstimo: {i}/{parcelas}', pmt, data_empr, session.get('id_usuario')))
            con.commit()
    finally:
        cursor.close()
    flash('Empréstimo confirmado com sucesso!', 'sucesso')
    return redirect(url_for('dashboard_simulacao'))


@app.route('/dashboard_historico', methods=['GET', 'POST'])
def dashboard_historico():
    if not session.get('usuario_logado'):
        flash('Faça login para acessar o histórico.', 'erro')
        return redirect(url_for('abrir_login'))
    if session.get('tipo_usuario') == 1:
        flash('Administradores não têm dashboard.', 'erro')
        return redirect(url_for('perfil_admin'))
    mes = datetime.now().month
    ano = datetime.now().year
    id_usuario = session.get('id_usuario')
    infos = atualizaHistorico(id_usuario, mes, ano)
    movimentacoes = infos["movimentacoes"]
    saldo = infos["saldo"]
    receita = infos["receita"]
    despesa = infos["despesa"]
    fixas = infos["fixas"]
    parcelas = infos["parcelas"]
    if request.args.get('mes'):
        mes = int(request.args.get('mes'))
    # Se não, verifica se veio pelo formulário (POST)
    elif request.method == 'POST' and request.form.get('mes'):
        mes = int(request.form.get('mes'))
    ano = datetime.now().year
    id_usuario = session.get('id_usuario')
    infos = atualizaHistorico(id_usuario, mes, ano)
    movimentacoes = infos["movimentacoes"]
    saldo = infos["saldo"]
    receita = infos["receita"]
    despesa = infos["despesa"]
    fixas = infos["fixas"]
    parcelas = infos["parcelas"]    
    return render_template('dashboard_historico.html', movimentacoes=movimentacoes, mes=mes, saldo=saldo, receita=receita, despesa=despesa, fixas=fixas, parcelas=parcelas)


@app.route('/dashboard/movimentacoes')
def dashboard_extrato():
    if not session.get('usuario_logado'):
        flash('Faça login para acessar as movimentações.', 'erro')
        return redirect(url_for('abrir_login'))
    if session.get('tipo_usuario') == 1:
        flash('Administradores não têm dashboard.', 'erro')
        return redirect(url_for('perfil_admin'))
    id_usuario = session.get('id_usuario')
    cursor = con.cursor()
    try:
        cursor.execute("""
            SELECT rPAD(DESCRICAO, 50, ' '), VALOR, DATA_ATUAL, ID_MOVIMENTACAO, TIPO
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1
            ORDER BY DATA_ATUAL DESC
        """, (id_usuario,))
        receitas = cursor.fetchall()

        cursor.execute("""
            SELECT rPAD(DESCRICAO, 50, ' '), VALOR, DATA_ATUAL, ID_MOVIMENTACAO, TIPO
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0
            ORDER BY DATA_ATUAL DESC
        """, (id_usuario,))
        despesas = cursor.fetchall()

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1
        """, (id_usuario,))
        total_receitas = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0
        """, (id_usuario,))
        total_despesas = cursor.fetchone()[0] or 0


    finally:
        cursor.close()

    return render_template('dashboard_extrato.html',
                           receitas=receitas,
                           despesas=despesas,
                           total_receitas=total_receitas,
                           total_despesas=total_despesas)

@app.route('/admin/dashboard/<cpf>')
def admin_dashboard(cpf):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))
    
    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]
        
        # Ano selecionado ou atual
        ano_selecionado = request.args.get('ano', datetime.now().year, type=int)

        # Dados totais
        cursor.execute("""
                       SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND CONDICAO = 1
                       """, (id_usuario,))
        total_receitas = cursor.fetchone()[0] or 0

        cursor.execute("""
                       SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND CONDICAO = 0
                       """, (id_usuario,))
        total_despesas = cursor.fetchone()[0] or 0

        saldo = total_receitas - total_despesas

        # Verificar se existem movimentações no ano selecionado
        cursor.execute("""
                       SELECT COUNT(*)
                       FROM MOVIMENTACAO
                       WHERE ID_USUARIO = ?
                         AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
                       """, (id_usuario, ano_selecionado))
        tem_movimentacoes_ano = cursor.fetchone()[0] > 0

        # Dados mensais para o gráfico de barras
        receitas_mensais = [0.0] * 12
        despesas_mensais = [0.0] * 12
        meses_nomes = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                       'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']

        # Buscar receitas (variáveis + fixas)
        for mes in range(1, 13):
            # Receitas variáveis do mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 1
                AND TIPO = 1
                AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            receitas_variaveis = float(cursor.fetchone()[0])

            # Receitas fixas acumuladas até este mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 1
                AND TIPO = 0
                AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            receitas_fixas = float(cursor.fetchone()[0])

            receitas_mensais[mes - 1] = receitas_variaveis + receitas_fixas

        # Buscar despesas (variáveis + fixas)
        for mes in range(1, 13):
            # Despesas variáveis do mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 0
                AND TIPO = 1
                AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            despesas_variaveis = float(cursor.fetchone()[0])

            # Despesas fixas acumuladas até este mês
            cursor.execute("""
                SELECT CAST(COALESCE(SUM(VALOR), 0) AS DOUBLE PRECISION)
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                AND CONDICAO = 0
                AND TIPO = 0
                AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
                AND EXTRACT(YEAR FROM DATA_ATUAL) = ?
            """, (id_usuario, mes, ano_selecionado))
            despesas_fixas = float(cursor.fetchone()[0])

            despesas_mensais[mes - 1] = despesas_variaveis + despesas_fixas

        # Criar gráfico de barras com Pygal
        grafico_svg = None

        if tem_movimentacoes_ano:
            bar_chart = pygal.Bar(
                height=400,
                width=800,
                explicit_size=True,
                title=f'Receitas e Despesas - {ano_selecionado}',
                x_title='Meses',
                y_title='Valor (R$)',
                show_legend=True,
                print_values=False,
                style=pygal.style.DefaultStyle(
                    colors=('#28a745', '#dc3545'),
                    background=('transparent')
                )
            )

            bar_chart.x_labels = meses_nomes
            bar_chart.add('Receitas', receitas_mensais)
            bar_chart.add('Despesas', despesas_mensais)
            grafico_svg = bar_chart.render(is_unicode=True)

    except Exception as e:
        flash(f'Erro ao gerar gráfico: {str(e)}', 'erro')
        grafico_svg = None
        receitas_mensais = []
        despesas_mensais = []
    finally:
        cursor.close()

    return render_template('dashboard.html',
                           total_receitas=total_receitas,
                           total_despesas=total_despesas,
                           saldo=saldo,
                           ano_selecionado=ano_selecionado,
                           grafico_svg=grafico_svg,
                           tem_movimentacoes_ano=tem_movimentacoes_ano,
                           admin_view=True,
                           usuario_view=usuario)

@app.route('/admin/dashboard_extrato/<cpf>')
def admin_dashboard_extrato(cpf):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]

        cursor.execute("""
            SELECT rPAD(DESCRICAO, 50, ' '), VALOR, DATA_ATUAL, ID_MOVIMENTACAO, TIPO
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1
            ORDER BY DATA_ATUAL DESC
        """, (id_usuario,))
        receitas = cursor.fetchall()

        cursor.execute("""
            SELECT rPAD(DESCRICAO, 50, ' '), VALOR, DATA_ATUAL, ID_MOVIMENTACAO, TIPO
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0
            ORDER BY DATA_ATUAL DESC
        """, (id_usuario,))
        despesas = cursor.fetchall()

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1
        """, (id_usuario,))
        total_receitas = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0
        """, (id_usuario,))
        total_despesas = cursor.fetchone()[0] or 0

    finally:
        cursor.close()

    return render_template('dashboard_extrato.html',
                           receitas=receitas,
                           despesas=despesas,
                           total_receitas=total_receitas,
                           total_despesas=total_despesas,
                           admin_view=True,
                           usuario_view=usuario)

@app.route('/admin/dashboard_historico/<cpf>', methods=['GET', 'POST'])
def admin_dashboard_historico(cpf):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]

        mes = datetime.now().month
        ano = datetime.now().year
        
        if request.method == 'POST':
            mes = int(request.form.get('mes'))
        
        infos = atualizaHistorico(id_usuario, mes, ano)
        movimentacoes = infos["movimentacoes"]
        saldo = infos["saldo"]
        receita = infos["receita"]
        despesa = infos["despesa"]
        fixas = infos["fixas"]
        parcelas = infos["parcelas"]

    finally:
        cursor.close()

    return render_template('dashboard_historico.html', 
                           movimentacoes=movimentacoes, 
                           mes=mes, 
                           saldo=saldo, 
                           receita=receita, 
                           despesa=despesa, 
                           fixas=fixas, 
                           parcelas=parcelas)

@app.route('/admin/dashboard_simulacao/<cpf>')
def admin_dashboard_simulacao(cpf):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        nome_usuario = usuario[1]

    finally:
        cursor.close()

    data_nf = datetime.now().strftime('%Y-%m-%d')
    data = datetime.strptime(data_nf, '%Y-%m-%d').date()
    return render_template('dashboard_simulacao.html', 
                           data=data)

@app.route('/admin/dashboard_simulacao_analise/<cpf>', methods=['POST'])
def admin_dashboard_simulacao_analise(cpf):
    if not session.get('usuario_logado'):
        flash('Faça login para acessar a simulação.', 'erro')
        return redirect(url_for('abrir_login'))
    cursor = con.cursor()
    try:
        cursor.execute("SELECT ID_USUARIO FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        id_usuario = usuario[0]
        etapa = 2
        mes = datetime.now().month
        valor = float(request.form['valor'])
        parcelas = int(request.form['parcelas'])
        data_nf = datetime.now().strftime('%Y-%m-%d')
        data = datetime.strptime(data_nf, '%Y-%m-%d').date()
        cursor.execute("""
            SELECT VALOR FROM TAXA WHERE DATA_FINAL IS NULL
        """)
        taxa = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1 AND TIPO = 1 AND EXTRACT(MONTH FROM DATA_ATUAL) = ?    
        """, (id_usuario, mes,))
        total_receitas = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0 AND TIPO = 1 AND EXTRACT(MONTH FROM DATA_ATUAL) = ?
        """, (id_usuario, mes,))
        total_despesas = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 1 AND TIPO = 0 AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?    
        """, (id_usuario, mes,))
        total_receitas += cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT CAST(SUM(VALOR) AS DOUBLE PRECISION)
            FROM MOVIMENTACAO
            WHERE ID_USUARIO = ? AND CONDICAO = 0 AND TIPO = 0 AND EXTRACT(MONTH FROM DATA_ATUAL) <= ?
        """, (id_usuario, mes,))
        total_despesas += cursor.fetchone()[0] or 0

        saldo = float(total_receitas) - float(total_despesas)

        if taxa > 0:
            pmt = valor * (float(taxa) / 100) / (1 - (1 + float(taxa) / 100) ** -parcelas)
        else:
            pmt = valor / parcelas

        if saldo <= 0:
            comprometimento = 100
        else:
            comprometimento = (pmt / saldo) * 100
        if comprometimento <= 20:
            risco = 'Baixo'
        elif 20 < comprometimento <= 35:
            risco = 'Médio'
        else:
            risco = 'Alto'
        valor_total = round(pmt * parcelas, 2)
    finally:
        cursor.close()
    return render_template('dashboard_simulacao.html', etapa=etapa, comprometimento=round(comprometimento, 2),
                           pmt=round(pmt, 2), parcelas=parcelas, risco=risco, valor_total=float(valor_total),
                           valor=valor, data=data)

@app.route('/admin/confirmar_emprestimo/<cpf>', methods=['POST'])
def admin_confirmar_emprestimo(cpf):
    if not session.get('usuario_logado'):
        flash('Faça login para confirmar o empréstimo.', 'erro')
        return redirect(url_for('abrir_login'))
    cursor = con.cursor()
    try:
        cursor.execute("SELECT ID_USUARIO FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        id_usuario = usuario[0]
        valor = float(request.form.get('valor'))
        parcelas = int(request.form.get('parcelas'))
        valor_total = float(request.form.get('valor_total'))
        pmt = float(request.form.get('pmt'))
        data = datetime.now().strftime('%Y-%m-%d')
        data_empr = datetime.strptime(data, '%Y-%m-%d').date()
        cursor.execute("""
            SELECT ID_TAXA FROM TAXA WHERE DATA_FINAL IS NULL
        """)
        id_taxa = cursor.fetchone()[0]
        cursor.execute("""
            INSERT INTO EMPRESTIMO (VALOR_TOTAL, QTD_PARCELA, SITUACAO, DATA_EMPRESTIMO, ID_USUARIO, ID_TAXA, VALOR_ORIGINAL)
            VALUES (?, ?, 0, ?, ?, ?, ?)""",
                       (valor_total, parcelas, data_empr, id_usuario, id_taxa, valor))
        con.commit()

        cursor.execute("""
            SELECT MAX(ID_EMPRESTIMO) FROM EMPRESTIMO WHERE ID_USUARIO = ?
        """, (id_usuario,))
        id_emprestimo = cursor.fetchone()[0]

        cursor.execute("""
            INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, DATA_ATUAL, CONDICAO, TIPO, ID_USUARIO)
            VALUES (?, ?, ?, 1, 2, ?)
            """, (f'Empréstimo', valor, data_empr, id_usuario))
        con.commit()

        con.commit()

        for i in range(1, parcelas + 1):
            data_empr += timedelta(days=30)
            cursor.execute("""
                INSERT INTO EMPRESTIMO_PARCELA (ID_EMPRESTIMO, VALOR_PARCELA, DATA_VENCIMENTO, SEQUENCIA_PARCELA)
                VALUES (?, ?, ?, ?)
                """, (id_emprestimo, pmt, data_empr, i))
            cursor.execute("""
            INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, DATA_ATUAL, CONDICAO, TIPO, ID_USUARIO)
            VALUES (?, ?, ?, 0, 2, ?)
            """, (f'Empréstimo: {i}/{parcelas}', pmt, data_empr, id_usuario))
            con.commit()
    finally:
        cursor.close()
    flash('Empréstimo confirmado com sucesso!', 'sucesso')
    return redirect(url_for('dashboard_simulacao'))

@app.route('/admin/cadastrar_receita/<cpf>', methods=['GET', 'POST'])
def admin_cadastrar_receita(cpf):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]

        if request.method == 'POST':
            descricao = request.form['descricao']
            valor = request.form['valor']
            tipo_mov = int(request.form['tipo'])  # 0 = fixo, 1 = variável
            
            # Validações
            if len(descricao) > 250:
                flash('Descrição muito longa.', 'erro')
                return redirect(url_for('admin_cadastrar_receita', cpf=cpf))
            
            if float(valor) >= 90000000000000000:
                flash('Valor muito alto.', 'erro')
                return redirect(url_for('admin_cadastrar_receita', cpf=cpf))

            cursor.execute("""
                INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, CONDICAO, TIPO, ID_USUARIO)
                VALUES (?, ?, 1, ?, ?)""",
                           (descricao, valor, tipo_mov, id_usuario))
            con.commit()
            
            flash(f'Receita cadastrada com sucesso para o usuário {nome_usuario}!', 'sucesso')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        return render_template('cadastrar_receita.html')
    finally:
        cursor.close()

@app.route('/admin/cadastrar_despesa/<cpf>', methods=['GET', 'POST'])
def admin_cadastrar_despesa(cpf):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]

        if request.method == 'POST':
            descricao = request.form['descricao']
            valor = request.form['valor']
            tipo_mov = int(request.form['tipo'])  # 0 = fixo, 1 = variável
            
            # Validações
            if len(descricao) > 250:
                flash('Descrição muito longa.', 'erro')
                return redirect(url_for('admin_cadastrar_despesa', cpf=cpf))
            
            if float(valor) >= 90000000000000000:
                flash('Valor muito alto.', 'erro')
                return redirect(url_for('admin_cadastrar_despesa', cpf=cpf))

            cursor.execute("""
                INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, CONDICAO, TIPO, ID_USUARIO)
                VALUES (?, ?, 0, ?, ?)""",
                           (descricao, valor, tipo_mov, id_usuario))
            con.commit()
            
            flash(f'Despesa cadastrada com sucesso para o usuário {nome_usuario}!', 'sucesso')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        return render_template('cadastrar_despesa.html',
                               admin_view=True,
                               usuario=usuario)
    finally:
        cursor.close()

@app.route('/admin/editar_receita/<cpf>/<int:id_movimentacao>', methods=['GET', 'POST'])
def admin_editar_receita(cpf, id_movimentacao):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]

        # Verificar se a movimentação pertence ao usuário
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO, DESCRICAO, VALOR, TIPO, CONDICAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 1
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Receita não encontrada ou não pertence a este usuário.', 'erro')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        if request.method == 'POST':
            descricao = request.form['descricao']
            if len(descricao) > 250:
                flash('Descrição muito longa.', 'erro')
                return redirect(url_for('admin_editar_receita', cpf=cpf, id_movimentacao=id_movimentacao))
            
            valor = request.form['valor']
            if float(valor) >= 90000000000000000:
                flash('Valor muito alto.', 'erro')
                return redirect(url_for('admin_editar_receita', cpf=cpf, id_movimentacao=id_movimentacao))
            
            tipo = int(request.form['tipo'])

            cursor.execute("""
                           UPDATE MOVIMENTACAO
                           SET DESCRICAO = ?,
                               VALOR     = ?,
                               TIPO      = ?
                           WHERE ID_MOVIMENTACAO = ?
                             AND ID_USUARIO = ?
                           """, (descricao, valor, tipo, id_movimentacao, id_usuario))

            con.commit()
            flash(f'Receita atualizada com sucesso para o usuário {nome_usuario}!', 'sucesso')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        return render_template('editar_receita.html',
                               id_movimentacao=movimentacao[0],
                               descricao=movimentacao[1],
                               valor=movimentacao[2],
                               tipo=movimentacao[3],
                               admin_view=True,
                               usuario=usuario)
    finally:
        cursor.close()

@app.route('/admin/editar_despesa/<cpf>/<int:id_movimentacao>', methods=['GET', 'POST'])
def admin_editar_despesa(cpf, id_movimentacao):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]

        # Verificar se a movimentação pertence ao usuário
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO, DESCRICAO, VALOR, TIPO, CONDICAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 0
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Despesa não encontrada ou não pertence a este usuário.', 'erro')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        if request.method == 'POST':
            descricao = request.form['descricao']
            if len(descricao) > 250:
                flash('Descrição muito longa.', 'erro')
                return redirect(url_for('admin_editar_despesa', cpf=cpf, id_movimentacao=id_movimentacao))
            
            valor = request.form['valor']
            if float(valor) >= 90000000000000000:
                flash('Valor muito alto.', 'erro')
                return redirect(url_for('admin_editar_despesa', cpf=cpf, id_movimentacao=id_movimentacao))
            
            tipo = int(request.form['tipo'])

            cursor.execute("""
                           UPDATE MOVIMENTACAO
                           SET DESCRICAO = ?,
                               VALOR     = ?,
                               TIPO      = ?
                           WHERE ID_MOVIMENTACAO = ?
                             AND ID_USUARIO = ?
                           """, (descricao, valor, tipo, id_movimentacao, id_usuario))

            con.commit()
            flash(f'Despesa atualizada com sucesso para o usuário {nome_usuario}!', 'sucesso')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        return render_template('editar_despesa.html',
                               id_movimentacao=movimentacao[0],
                               descricao=movimentacao[1],
                               valor=movimentacao[2],
                               tipo=movimentacao[3],
                               admin_view=True,
                               usuario=usuario)
    finally:
        cursor.close()

@app.route('/admin/deletar_receita/<cpf>/<int:id_movimentacao>', methods=['GET', 'POST'])
def admin_deletar_receita(cpf, id_movimentacao):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]

        # Verificar se a movimentação pertence ao usuário
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 1
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Receita não encontrada ou não pertence a este usuário.', 'erro')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        cursor.execute("""
                       DELETE FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                       """, (id_movimentacao, id_usuario))
        con.commit()
        flash(f'Receita deletada com sucesso para o usuário {nome_usuario}!', 'sucesso')
        
    finally:
        cursor.close()

    return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

@app.route('/admin/deletar_despesa/<cpf>/<int:id_movimentacao>', methods=['GET', 'POST'])
def admin_deletar_despesa(cpf, id_movimentacao):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso restrito a administradores.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        # Buscar dados do usuário
        cursor.execute("SELECT ID_USUARIO, NOME FROM USUARIO WHERE CPF = ?", (cpf,))
        usuario = cursor.fetchone()
        
        if not usuario:
            flash('Usuário não encontrado.', 'erro')
            return redirect(url_for('perfil_admin'))
        
        id_usuario = usuario[0]
        nome_usuario = usuario[1]

        # Verificar se a movimentação pertence ao usuário
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 0
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Despesa não encontrada ou não pertence a este usuário.', 'erro')
            return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

        cursor.execute("""
                       DELETE FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                       """, (id_movimentacao, id_usuario))
        con.commit()
        flash(f'Despesa deletada com sucesso para o usuário {nome_usuario}!', 'sucesso')
        
    finally:
        cursor.close()

    return redirect(url_for('admin_dashboard_extrato', cpf=cpf))

@app.route('/movimentacoes/cadastrar_despesa', methods=['GET', 'POST'])
def cadastrar_despesa():
    if not session.get('usuario_logado'):
        flash('Faça login para cadastrar despesa.', 'erro')
        return redirect(url_for('abrir_login'))
    if request.method == 'POST':
        descricao = request.form['descricao']
        if len(descricao) > 250:
            flash('Descrição muito longa para despesa.', 'erro')
            return redirect(url_for('cadastrar_despesa'))
        valor = request.form['valor']
        valor_int = int(valor)
        if valor_int >= 90000000000000000:
            flash('Valor muito alto para despesa.', 'erro')
            return redirect(url_for('cadastrar_despesa'))
        tipo = int(request.form['tipo'])
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, CONDICAO, TIPO, ID_USUARIO)
                VALUES (?, ?, 0, ?, ?)""",
                           (descricao, valor, tipo, session.get('id_usuario')))
            con.commit()
            flash('Despesa cadastrada com sucesso!', 'sucesso')
            return redirect(url_for('dashboard_extrato'))
        finally:
            cursor.close()
    return render_template('cadastrar_despesa.html')


@app.route('/movimentacoes/cadastrar_receita', methods=['GET', 'POST'])
def cadastrar_receita():
    if not session.get('usuario_logado'):
        flash('Faça login para cadastrar receita.', 'erro')
        return redirect(url_for('abrir_login'))
    if request.method == 'POST':
        descricao = request.form['descricao']
        if len(descricao) > 250:
            flash('Descrição muito longa para receita.', 'erro')
            return redirect(url_for('cadastrar_receita'))
        valor = request.form['valor']
        if int(valor) >= 90000000000000000:
            flash('Valor muito alto para receita.', 'erro')
            return redirect(url_for('cadastrar_receita'))
        tipo = int(request.form['tipo'])  # 0 = fixo, 1 = variável
        cursor = con.cursor()
        try:
            cursor.execute("""
                INSERT INTO MOVIMENTACAO (DESCRICAO, VALOR, CONDICAO, TIPO, ID_USUARIO)
                VALUES (?, ?, 1, ?, ?)""",
                           (descricao, valor, tipo, session.get('id_usuario')))
            con.commit()
            flash('Receita cadastrada com sucesso!', 'sucesso')
            return redirect(url_for('dashboard_extrato'))
        finally:
            cursor.close()
    return render_template('cadastrar_receita.html')


@app.route('/admin/adicionar_taxa')
def visualizar_adicionar_taxa():
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso negado.', 'erro')
        return redirect(url_for('index'))
    return render_template('adicionar_taxa.html')


@app.route('/admin/cadastrar_taxa', methods=['POST'])
def cadastrar_taxa():
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso negado: somente administradores podem cadastrar taxas.', 'erro')
        return redirect(url_for('index'))

    descricao = request.form.get('descricao')
    valor = request.form.get('valor')

    cursor = con.cursor()
    try:
        # Checa se já existe uma taxa cadastrada hoje
        cursor.execute("""
            SELECT 1 FROM TAXA WHERE DATA_INICIO = CURRENT_DATE
        """)
        existe_taxa_hoje = cursor.fetchone()

        if existe_taxa_hoje:
            flash('Já existe uma taxa cadastrada hoje. Só é permitido cadastrar uma taxa por dia.', 'erro')
            return redirect(url_for('visualizar_adicionar_taxa'))

        # Atualiza a anterior e cadastra uma nova
        cursor.execute("""
            UPDATE TAXA
            SET DATA_FINAL = CURRENT_DATE
            WHERE DATA_FINAL IS NULL
        """)
        cursor.execute("""
            INSERT INTO TAXA (DESCRICAO, VALOR, DATA_INICIO, DATA_FINAL)
            VALUES (?, ?, CURRENT_DATE, NULL)
        """, (descricao, valor))

        con.commit()
        flash('Taxa cadastrada com sucesso!', 'sucesso')
        return redirect(url_for('perfil_admin'))
    except:
        flash(f'Erro ao cadastrar taxa', 'erro')
        return redirect(url_for('visualizar_adicionar_taxa'))
    finally:
        cursor.close()


@app.route('/movimentacoes/editar_receita/<int:id_movimentacao>', methods=['GET', 'POST'])
def editar_receita(id_movimentacao):
    if not session.get('usuario_logado'):
        flash('Faça login para editar receita.', 'erro')
        return redirect(url_for('abrir_login'))

    id_usuario = session.get('id_usuario')
    cursor = con.cursor()

    try:
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO, DESCRICAO, VALOR, TIPO, CONDICAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 1
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Receita não encontrada ou você não tem permissão para editá-la.', 'erro')
            return redirect(url_for('dashboard_extrato'))

        if request.method == 'POST':
            descricao = request.form['descricao']
            if len(descricao) > 250:
                flash('Descrição muito longa para despesa.', 'erro')
                return redirect(url_for('cadastrar_despesa'))
            valor = request.form['valor']
            if int(valor) >= 90000000000000000:
                flash('Valor muito alto para despesa.', 'erro')
                return redirect(url_for('cadastrar_despesa'))
            tipo = int(request.form['tipo'])

            cursor.execute("""
                           UPDATE MOVIMENTACAO
                           SET DESCRICAO = ?,
                               VALOR     = ?,
                               TIPO      = ?
                           WHERE ID_MOVIMENTACAO = ?
                             AND ID_USUARIO = ?
                           """, (descricao, valor, tipo, id_movimentacao, id_usuario))

            con.commit()
            flash('Receita atualizada com sucesso!', 'sucesso')
            return redirect(url_for('dashboard_extrato'))

        return render_template('editar_receita.html',
                               id_movimentacao=movimentacao[0],
                               descricao=movimentacao[1],
                               valor=movimentacao[2],
                               tipo=movimentacao[3])
    finally:
        cursor.close()


@app.route('/movimentacoes/editar_despesa/<int:id_movimentacao>', methods=['GET', 'POST'])
def editar_despesa(id_movimentacao):
    if not session.get('usuario_logado'):
        flash('Faça login para editar despesa.', 'erro')
        return redirect(url_for('abrir_login'))

    id_usuario = session.get('id_usuario')
    cursor = con.cursor()

    try:
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO, DESCRICAO, VALOR, TIPO, CONDICAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 0
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Despesa não encontrada ou você não tem permissão para editá-la.', 'erro')
            return redirect(url_for('dashboard_extrato'))

        if request.method == 'POST':
            descricao = request.form['descricao']
            if len(descricao) > 250:
                flash('Descrição muito longa para despesa.', 'erro')
                return redirect(url_for('cadastrar_despesa'))
            valor = request.form['valor']
            if int(valor) >= 90000000000000000:
                flash('Valor muito alto para despesa.', 'erro')
                return redirect(url_for('cadastrar_despesa'))
            tipo = int(request.form['tipo'])

            cursor.execute("""
                           UPDATE MOVIMENTACAO
                           SET DESCRICAO = ?,
                               VALOR     = ?,
                               TIPO      = ?
                           WHERE ID_MOVIMENTACAO = ?
                             AND ID_USUARIO = ?
                           """, (descricao, valor, tipo, id_movimentacao, id_usuario))

            con.commit()
            flash('Despesa atualizada com sucesso!', 'sucesso')
            return redirect(url_for('dashboard_extrato'))

        return render_template('editar_despesa.html',
                               id_movimentacao=movimentacao[0],
                               descricao=movimentacao[1],
                               valor=movimentacao[2],
                               tipo=movimentacao[3])
    finally:
        cursor.close()


@app.route('/movimentacoes/deletar_receita/<int:id_movimentacao>', methods=['GET', 'POST'])
def deletar_receita(id_movimentacao):
    if not session.get('usuario_logado'):
        flash('Faça login para deletar receita.', 'erro')
        return redirect(url_for('abrir_login'))

    id_usuario = session.get('id_usuario')
    cursor = con.cursor()

    try:
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 1
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Receita não encontrada ou você não tem permissão para deletá-la.', 'erro')
            return redirect(url_for('dashboard_extrato'))

        cursor.execute("""
                       DELETE FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                       """, (id_movimentacao, id_usuario))
        con.commit()
        flash('Receita deletada com sucesso!', 'sucesso')
    finally:
        cursor.close()

    return redirect(url_for('dashboard_extrato'))


@app.route('/movimentacoes/deletar_despesa/<int:id_movimentacao>', methods=['GET', 'POST'])
def deletar_despesa(id_movimentacao):
    if not session.get('usuario_logado'):
        flash('Faça login para deletar despesa.', 'erro')
        return redirect(url_for('abrir_login'))

    id_usuario = session.get('id_usuario')
    cursor = con.cursor()

    try:
        # Verificar se a despesa pertence ao usuário e se é despesa (CONDICAO = 0)
        cursor.execute("""
                       SELECT ID_MOVIMENTACAO
                       FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                         AND CONDICAO = 0
                       """, (id_movimentacao, id_usuario))

        movimentacao = cursor.fetchone()

        if not movimentacao:
            flash('Despesa não encontrada ou você não tem permissão para deletá-la.', 'erro')
            return redirect(url_for('dashboard_extrato'))

        cursor.execute("""
                       DELETE FROM MOVIMENTACAO
                       WHERE ID_MOVIMENTACAO = ?
                         AND ID_USUARIO = ?
                       """, (id_movimentacao, id_usuario))
        con.commit()
        flash('Despesa deletada com sucesso!', 'sucesso')
    finally:
        cursor.close()
    return redirect(url_for('dashboard_extrato'))


@app.route('/admin/editar_taxa/<int:id_taxa>', methods=['GET', 'POST'])
def editar_taxa(id_taxa):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso negado: somente administradores podem editar taxas.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()

    try:
        cursor.execute("SELECT ID_TAXA, DESCRICAO, VALOR FROM TAXA WHERE ID_TAXA = ?", (id_taxa,))
        taxa = cursor.fetchone()

        if not taxa:
            flash('Taxa não encontrada.', 'erro')
            return redirect(url_for('perfil_admin'))

        if request.method == 'POST':
            descricao = request.form.get('descricao')
            valor = request.form.get('valor')

            # CORRIGIDO: ID -> ID_TAXA
            cursor.execute("""
                           UPDATE TAXA
                           SET DESCRICAO = ?,
                               VALOR     = ?
                           WHERE ID_TAXA = ?
                           """, (descricao, valor, id_taxa))
            con.commit()
            flash('Taxa editada com sucesso!', 'sucesso')
            return redirect(url_for('perfil_admin'))

        return render_template('editar_taxa.html', taxa=taxa)

    except:
        flash(f'Erro ao editar taxa ', 'erro')
        return redirect(url_for('perfil_admin'))
    finally:
        cursor.close()


@app.route('/admin/deletar_taxa/<int:id_taxa>', methods=['GET', 'POST'])
def deletar_taxa(id_taxa):
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso negado: somente administradores podem deletar taxas.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        cursor.execute("SELECT ID_TAXA, DESCRICAO, VALOR FROM TAXA WHERE ID_TAXA = ?", (id_taxa,))
        taxa = cursor.fetchone()

        if not taxa:
            flash('Taxa não encontrada.', 'erro')
            return redirect(url_for('perfil_admin'))

        cursor.execute("DELETE FROM TAXA WHERE ID_TAXA = ?", (id_taxa,))
        con.commit()
        flash('Taxa excluída com sucesso!', 'sucesso')
        return redirect(url_for('perfil_admin'))
    except:
        flash(f'Erro ao excluir taxa ', 'erro')
        return redirect(url_for('perfil_admin'))
    finally:
        cursor.close()


@app.route('/gerar_relatorio_usuario/<cpf>')
def gerar_relatorio_usuario(cpf=None):
    if not session.get('usuario_logado'):
        flash('Faça login para gerar o relatório.', 'erro')
        return redirect(url_for('abrir_login'))

    cursor = con.cursor()
    if session.get('tipo_usuario') == 0:
        print('nao virei adm')
        id_usuario = session.get('id_usuario')
        nome = session.get('nome_usuario')
        cpf = session.get('cpf_usuario')
        try:
            cursor.execute("""
                SELECT DESCRICAO, VALOR, DATA_ATUAL, CONDICAO
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                ORDER BY DATA_ATUAL ASC
            """, (id_usuario,))
            movimentacoes = cursor.fetchall()
        finally:
            cursor.close()
    else:
        try:
            cursor.execute("""
                SELECT ID_USUARIO, NOME
                FROM USUARIO
                WHERE CPF = ?
            """, (cpf,))
            usuario = cursor.fetchone()
            if usuario is None:
                flash('Usuário não encontrado para o CPF fornecido.', 'erro')
                return redirect(url_for('perfil_admin'))
            id_usuario = usuario[0]
            nome = usuario[1]
            cursor.execute("""
                SELECT DESCRICAO, VALOR, DATA_ATUAL, CONDICAO
                FROM MOVIMENTACAO
                WHERE ID_USUARIO = ?
                ORDER BY DATA_ATUAL ASC
            """, (id_usuario,))
            movimentacoes = cursor.fetchall()
        finally:
            cursor.close()

    if movimentacoes is None or len(movimentacoes) == 0:
        flash('Nenhuma movimentação encontrada para gerar o relatório.', 'erro')
        return redirect(url_for('abrir_login'))
    else:
        class PDF(FPDF):
            def footer(self):
                self.set_y(-15)
                self.set_font('Arial', 'I', 9)
                self.set_text_color(128)
                data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
                self.cell(0, 10, f"Gerado em {data_geracao}", 0, 0, 'C')

        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=20)

        # --- LOGO NO TOPO ---
        try:
            pdf.image("static/img/logo_escura.png", x=10, y=8, w=25)
        except:
            pass  # Se o arquivo não existir, apenas ignora

        # Dá um pequeno espaço após o logo
        pdf.ln(15)

        # --- CABEÇALHO VERDE ---
        pdf.set_fill_color(63, 161, 16)  # #3FA110
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", "B", 18)  # Fonte um pouco maior
        pdf.cell(0, 20, "Extrato do Usuário", ln=True, align="C", fill=True)

        pdf.ln(10)

        # Nome e CPF
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(25, 10, "Nome:", 0, 0)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, nome, ln=True)

        pdf.set_font("Arial", "B", 12)
        pdf.cell(25, 10, "CPF:", 0, 0)
        pdf.set_font("Arial", "", 12)
        pdf.cell(0, 10, cpf, ln=True)

        pdf.ln(8)

        # Cabeçalho da tabela
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(200, 200, 200)
        pdf.cell(90, 10, "Descrição", 1, 0, "C", fill=True)
        pdf.cell(40, 10, "Valor", 1, 0, "C", fill=True)
        pdf.cell(50, 10, "Data", 1, 1, "C", fill=True)

        # Linhas da tabela
        pdf.set_font("Arial", "", 11)
        fill = False
        total_receitas = 0
        total_despesas = 0

        for desc, valor, data, condicao in movimentacoes:
            # Alternar fundo da linha (zebra)
            fill_color = (215, 215, 215) if fill else (255, 255, 255)
            pdf.set_fill_color(*fill_color)

            # Define cores e sinal conforme a condição
            if condicao == 0:  # Despesa
                valor = -abs(valor)
                # valor_cor = (255, 150, 150)  # vermelho claro
                total_despesas += abs(valor)
            else:  # Receita
                valor = abs(valor)
                # valor_cor = (150, 255, 150)  # verde claro
                total_receitas += valor

            # Descrição
            pdf.cell(90, 10, str(desc), 1, 0, "L", fill=True)

            # Valor com cor de fundo (vermelho ou verde)
            # pdf.set_fill_color(*valor_cor)
            pdf.cell(40, 10, f"R$ {valor:,.2f}", 1, 0, "R", fill=True)

            # Data normal
            pdf.set_fill_color(*fill_color)
            pdf.cell(50, 10, str(data.strftime('%d/%m/%Y')), 1, 1, "C", fill=True)

            fill = not fill  # alternar cor de fundo

        pdf.ln(5)

        # Totais e saldo
        saldo_total = total_receitas - total_despesas
        pdf.set_font("Arial", "B", 12)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(90, 10, "Total de Receitas:", 1, 0, "R", fill=True)
        pdf.cell(40, 10, f"R$ {total_receitas:,.2f}", 1, 0, "R", fill=True)
        pdf.cell(50, 10, " ", 1, 1, "C", fill=True)

        pdf.cell(90, 10, "Total de Despesas:", 1, 0, "R", fill=True)
        pdf.cell(40, 10, f"R$ {total_despesas:,.2f}", 1, 0, "R", fill=True)
        pdf.cell(50, 10, " ", 1, 1, "C", fill=True)

        pdf.cell(90, 10, "Saldo Final:", 1, 0, "R", fill=True)
        pdf.cell(40, 10, f"R$ {saldo_total:,.2f}", 1, 0, "R", fill=True)
        pdf.cell(50, 10, " ", 1, 1, "C", fill=True)

        caminho_pdf = f"relatorio_{id_usuario}.pdf"
        pdf.output(caminho_pdf)

        return send_file(caminho_pdf, as_attachment=True)


@app.route('/gerar_relatorio_emprestimos')
def gerar_relatorio_emprestimos():
    # Verifica se o usuário está logado e é admin
    if not session.get('usuario_logado') or session.get('tipo_usuario') != 1:
        flash('Acesso negado. Apenas administradores podem gerar este relatório.', 'erro')
        return redirect(url_for('index'))

    cursor = con.cursor()
    try:
        cursor.execute("""
            SELECT U.NOME, U.CPF, E.ID_EMPRESTIMO, E.VALOR_ORIGINAL, E.VALOR_TOTAL, 
                   E.QTD_PARCELA, E.DATA_EMPRESTIMO
            FROM EMPRESTIMO E
            JOIN USUARIO U ON E.ID_USUARIO = U.ID_USUARIO
            ORDER BY U.NOME ASC, E.DATA_EMPRESTIMO DESC
        """)
        emprestimos = cursor.fetchall()
    finally:
        cursor.close()

    if not emprestimos:
        flash('Nenhum empréstimo encontrado.', 'erro')
        return redirect(url_for('perfil_admin'))

    class PDF(FPDF):
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 9)
            self.set_text_color(128)
            data_geracao = datetime.now().strftime("%d/%m/%Y %H:%M")
            self.cell(0, 10, f"Gerado em {data_geracao}", 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=20)

    # --- LOGO NO TOPO ---
    try:
        pdf.image("static/img/logo_escura.png", x=10, y=8, w=25)
    except:
        pass

    pdf.ln(15)

    # --- CABEÇALHO VERDE ---
    pdf.set_fill_color(63, 161, 16)  # #3FA110
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 18)
    pdf.cell(0, 20, "Relatório de Empréstimos por Usuário", ln=True, align="C", fill=True)
    pdf.ln(10)

    pdf.set_text_color(0, 0, 0)
    usuario_atual = None
    fill = False

    for nome, cpf, id_emp, valor_original, valor_total, parcelas, data_emp in emprestimos:
        # Quando o usuário muda, adiciona cabeçalho novo
        if usuario_atual != cpf:
            if usuario_atual is not None:
                pdf.ln(5)
            usuario_atual = cpf

            # Nome e CPF do usuário
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, f"{nome} - {cpf}", ln=True)

            # Cabeçalho da tabela para este usuário
            pdf.set_font("Arial", "B", 11)
            pdf.set_fill_color(200, 200, 200)
            pdf.cell(25, 10, "ID", 1, 0, "C", fill=True)
            pdf.cell(40, 10, "Valor Original", 1, 0, "C", fill=True)
            pdf.cell(40, 10, "Valor Total", 1, 0, "C", fill=True)
            pdf.cell(30, 10, "Parcelas", 1, 0, "C", fill=True)
            pdf.cell(45, 10, "Data Empréstimo", 1, 1, "C", fill=True)
            pdf.set_font("Arial", "", 10)

        # Fundo da linha (zebra)
        fill_color = (245, 245, 245) if fill else (255, 255, 255)
        pdf.set_fill_color(*fill_color)

        # Linhas com dados
        pdf.cell(25, 10, str(id_emp), 1, 0, "C", fill=True)
        pdf.cell(40, 10, f"R$ {valor_original:,.2f}", 1, 0, "R", fill=True)
        pdf.cell(40, 10, f"R$ {valor_total:,.2f}", 1, 0, "R", fill=True)
        pdf.cell(30, 10, str(parcelas), 1, 0, "C", fill=True)
        pdf.cell(45, 10, str(data_emp.strftime('%d/%m/%Y')), 1, 1, "C", fill=True)

        fill = not fill  # alternar cor da linha

    pdf.ln(5)

    caminho_pdf = "relatorio_emprestimos_por_usuario.pdf"
    pdf.output(caminho_pdf)

    return send_file(caminho_pdf, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)