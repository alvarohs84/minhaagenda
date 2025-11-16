# --- main.py ---
# [VERSÃO FINAL] Login, Multi-Usuário, Repetições e Correções de Fuso Horário

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Enum as PyEnum
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.orm import declarative_base 
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import List, Optional
from datetime import datetime, date, timedelta
import os
from dateutil.rrule import rrule, rrulestr, rrulebase
from dateutil.relativedelta import relativedelta
import datetime as dt # Para o timezone
from passlib.context import CryptContext # Para senhas
from jose import JWTError, jwt # Para tokens
from email_validator import validate_email, EmailNotValidError # Para validar email

# --- 1. CONFIGURAÇÃO DE SEGURANÇA (Tokens) ---
SECRET_KEY = "sua_chave_secreta_muito_longa_e_dificil" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- 2. CONFIGURAÇÃO DO BANCO DE DADOS ---
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL")

if SQLALCHEMY_DATABASE_URL is None:
    print("ALERTA: DATABASE_URL não encontrada, usando SQLite local (temporário).")
    SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
elif SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 3. MODELS (Definição das Tabelas do Banco) ---

class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    pacientes = relationship("Paciente", back_populates="owner")
    agendamentos = relationship("Agendamento", back_populates="owner")

class Paciente(Base):
    __tablename__ = 'pacientes'
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=False)
    telefone = Column(String, nullable=True)
    data_nascimento = Column(DateTime, nullable=True) 
    sexo = Column(String, nullable=True)
    diagnostico_medico = Column(String, nullable=True)
    avaliacao = Column(Text, nullable=True) 

    user_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    owner = relationship("Usuario", back_populates="pacientes")

    agendamentos = relationship("Agendamento", back_populates="paciente", cascade="all, delete-orphan")
    evolucoes = relationship("Evolucao", back_populates="paciente", cascade="all, delete-orphan")

class Agendamento(Base):
    __tablename__ = 'agendamentos'
    id = Column(Integer, primary_key=True, index=True)
    data_hora_inicio = Column(DateTime(timezone=True), nullable=False)
    data_hora_fim = Column(DateTime(timezone=True), nullable=False)
    status = Column(PyEnum('Agendado', 'Presente', 'Cancelado', name='status_agendamento'), default='Agendado')

    paciente_id = Column(Integer, ForeignKey('pacientes.id', ondelete="CASCADE"), nullable=False)
    rrule = Column(String, nullable=True) 
    exdates = Column(Text, nullable=True) 

    user_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    owner = relationship("Usuario", back_populates="agendamentos")

    paciente = relationship("Paciente", back_populates="agendamentos")
    evolucao = relationship("Evolucao", uselist=False, back_populates="agendamento", cascade="all, delete-orphan")

class Evolucao(Base):
    __tablename__ = 'evolucoes'
    id = Column(Integer, primary_key=True, index=True)
    texto_evolucao = Column(Text, nullable=False)
    data_criacao = Column(DateTime(timezone=True), default=datetime.utcnow)

    agendamento_id = Column(Integer, ForeignKey('agendamentos.id'), nullable=False)
    paciente_id = Column(Integer, ForeignKey('pacientes.id'), nullable=False)

    user_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)

    agendamento = relationship("Agendamento", back_populates="evolucao")
    paciente = relationship("Paciente", back_populates="evolucoes")

# Cria as tabelas
Base.metadata.create_all(bind=engine)

# --- 4. SCHEMAS (Pydantic - Validação de dados da API) ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserSchema(BaseModel):
    id: int
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class PacienteBase(BaseModel):
    nome: str
    telefone: Optional[str] = None
    data_nascimento: Optional[date] = None
    sexo: Optional[str] = None
    diagnostico_medico: Optional[str] = None
    avaliacao: Optional[str] = None

class PacienteCreate(PacienteBase):
    pass

class PacienteSchema(PacienteBase):
    id: int
    user_id: int
    model_config = ConfigDict(from_attributes=True)

class EvolucaoCreate(BaseModel):
    texto_evolucao: str

class AgendamentoCreate(BaseModel):
    paciente_id: int
    data_hora_inicio: datetime
    data_hora_fim: datetime
    rrule: Optional[str] = None 

class AgendamentoUpdate(BaseModel):
    data_hora_inicio: datetime
    data_hora_fim: datetime

class AgendamentoSchema(BaseModel):
    id: int
    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: str
    paciente: PacienteSchema 
    rrule: Optional[str] = None 
    exdates: Optional[str] = None 
    user_id: int

    model_config = ConfigDict(from_attributes=True)

class OcorrenciaUpdate(BaseModel):
    data_original: datetime 
    novo_inicio: datetime
    novo_fim: datetime

class OcorrenciaStatus(BaseModel):
    data_ocorrencia: datetime
    novo_status: str

class DashboardSessao(BaseModel):
    nome_paciente: str
    total_sessoes: int

class EvolucaoSchema(BaseModel):
    id: int
    texto_evolucao: str
    data_criacao: datetime
    user_id: int
    model_config = ConfigDict(from_attributes=True)

# --- 5. INICIALIZAÇÃO DO APP E CORS ---

app = FastAPI(title="Minha Agenda API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

# --- 6. DEPENDÊNCIAS E FUNÇÕES DE SEGURANÇA ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = db.query(Usuario).filter(Usuario.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user

# --- 7. ROTAS DE AUTENTICAÇÃO ---

@app.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    try:
        validate_email(user.email)
    except EmailNotValidError as e:
        raise HTTPException(status_code=400, detail=f"Email inválido: {e}")

    db_user = db.query(Usuario).filter(Usuario.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email já registrado")

    hashed_password = get_password_hash(user.password)
    db_user = Usuario(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserSchema)
async def read_users_me(current_user: Usuario = Depends(get_current_user)):
    return current_user


# --- 8. ROTAS PROTEGIDAS DA APLICAÇÃO ---

# --- Rotas de PACIENTE ---

@app.post("/pacientes", response_model=PacienteSchema, status_code=status.HTTP_201_CREATED)
def criar_paciente(paciente: PacienteCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    data_nasc = datetime.combine(paciente.data_nascimento, datetime.min.time()) if paciente.data_nascimento else None

    db_paciente = Paciente(
        **paciente.model_dump(),
        data_nascimento=data_nasc,
        user_id=current_user.id 
    )
    db.add(db_paciente)
    db.commit()
    db.refresh(db_paciente)
    return db_paciente

@app.get("/pacientes", response_model=List[PacienteSchema])
def listar_pacientes(db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    pacientes = db.query(Paciente).filter(Paciente.user_id == current_user.id).all() 
    return pacientes

@app.patch("/pacientes/{paciente_id}", response_model=PacienteSchema)
def atualizar_paciente(paciente_id: int, paciente: PacienteCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.user_id == current_user.id).first() 
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente not found")

    dados_paciente = paciente.model_dump(exclude_unset=True)

    if 'data_nascimento' in dados_paciente:
        if dados_paciente['data_nascimento']:
            db_paciente.data_nascimento = datetime.combine(dados_paciente['data_nascimento'], datetime.min.time())
        else:
            db_paciente.data_nascimento = None
        del dados_paciente['data_nascimento'] 

    for key, value in dados_paciente.items():
        setattr(db_paciente, key, value)

    db.commit()
    db.refresh(db_paciente)
    return db_paciente

@app.delete("/pacientes/{paciente_id}", status_code=status.HTTP_200_OK)
def deletar_paciente(paciente_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.user_id == current_user.id).first() 
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente not found")

    try:
        db.delete(db_paciente)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Erro ao deletar: Este paciente pode ter agendamentos. {e}")

    return {"detail": "Paciente deletado com sucesso"}

# --- Rotas de AGENDAMENTO ---

@app.get("/agendamentos", response_model=List[AgendamentoSchema])
def listar_agendamentos(start: datetime, end: datetime, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    agendamentos_base = db.query(Agendamento).filter(Agendamento.user_id == current_user.id).all() 

    eventos_finais = []
    tz = dt.timezone.utc 

    start_naive = start.replace(tzinfo=None)
    end_naive = end.replace(tzinfo=None)

    for evento in agendamentos_base:
        evento_start_naive = evento.data_hora_inicio.replace(tzinfo=None)
        evento_end_naive = evento.data_hora_fim.replace(tzinfo=None)

        if not evento.rrule:
            if evento_start_naive < end_naive and evento_end_naive > start_naive:
                eventos_finais.append(evento)
        else:
            dtstart_naive = evento_start_naive

            regra = rrulestr(evento.rrule, dtstart=dtstart_naive) 
            duracao = evento_end_naive - evento_start_naive

            excecoes = []
            if evento.exdates:
                excecoes_str = evento.exdates.split(',')
                for ex_str in excecoes_str:
                    try:
                        excecoes.append(datetime.fromisoformat(ex_str).replace(tzinfo=None))
                    except ValueError:
                        pass 

            limite_futuro_naive = datetime.utcnow() + relativedelta(years=2)

            if end_naive > limite_futuro_naive:
                end_naive = limite_futuro_naive

            ocorrencias = regra.between(start_naive, end_naive, inc=True)

            for inicio_naive in ocorrencias:
                if inicio_naive in excecoes:
                    continue

                fim_naive = inicio_naive + duracao

                evento_virtual = Agendamento(
                    id=evento.id,
                    data_hora_inicio=inicio_naive.replace(tzinfo=tz),
                    data_hora_fim=fim_naive.replace(tzinfo=tz),
                    status=evento.status,
                    paciente_id=evento.paciente_id,
                    rrule=evento.rrule,
                    exdates=evento.exdates,
                    paciente=evento.paciente,
                    user_id=evento.user_id
                )
                eventos_finais.append(evento_virtual)

    return eventos_finais

@app.post("/agendamentos", response_model=AgendamentoSchema, status_code=status.HTTP_201_CREATED)
def criar_agendamento(agendamento: AgendamentoCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_paciente = db.query(Paciente).filter(Paciente.id == agendamento.paciente_id, Paciente.user_id == current_user.id).first()
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente not found")

    db_agendamento = Agendamento(
        paciente_id=agendamento.paciente_id,
        data_hora_inicio=agendamento.data_hora_inicio,
        data_hora_fim=agendamento.data_hora_fim,
        status='Agendado',
        rrule=agendamento.rrule,
        user_id=current_user.id
    )
    db.add(db_agendamento)
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento

@app.patch("/agendamentos/{agendamento_id}", response_model=AgendamentoSchema)
def atualizar_data_agendamento(agendamento_id: int, update_data: AgendamentoUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id, Agendamento.user_id == current_user.id, Agendamento.rrule == None).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento não-recorrente não encontrado")

    try:
        update_data_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_data_dict.items():
            setattr(db_agendamento, key, value)
        db.commit() 
        db.refresh(db_agendamento)
        return db_agendamento
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco: {e}")

@app.delete("/agendamentos/{agendamento_id}", status_code=status.HTTP_200_OK)
def deletar_agendamento(agendamento_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id, Agendamento.user_id == current_user.id).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento not found")

    db.delete(db_agendamento)
    db.commit()
    return {"detail": "Agendamento deletado com sucesso"}

# --- Rotas de AÇÕES (Check-in, Cancelar) ---

@app.post("/agendamentos/{agendamento_id}/mover_ocorrencia", response_model=AgendamentoSchema)
def mover_ocorrencia(agendamento_id: int, update: OcorrenciaUpdate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    regra_pai = db.query(Agendamento).filter(Agendamento.id == agendamento_id, Agendamento.user_id == current_user.id).first()
    if regra_pai is None or regra_pai.rrule is None:
        raise HTTPException(status_code=404, detail="Regra de agendamento não encontrada")

    data_excecao_str = update.data_original.isoformat()
    if regra_pai.exdates:
        if data_excecao_str not in regra_pai.exdates:
            regra_pai.exdates += f",{data_excecao_str}"
    else:
        regra_pai.exdates = data_excecao_str

    db.commit()

    novo_agendamento_unico = Agendamento(
        paciente_id=regra_pai.paciente_id,
        data_hora_inicio=update.novo_inicio,
        data_hora_fim=update.novo_fim,
        status='Agendado',
        rrule=None, 
        user_id=current_user.id
    )
    db.add(novo_agendamento_unico)
    db.commit()
    db.refresh(novo_agendamento_unico)

    return novo_agendamento_unico

@app.post("/agendamentos/{agendamento_id}/status_ocorrencia", response_model=AgendamentoSchema)
def status_ocorrencia(agendamento_id: int, update: OcorrenciaStatus, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    regra_pai = db.query(Agendamento).filter(Agendamento.id == agendamento_id, Agendamento.user_id == current_user.id).first()
    if regra_pai is None or regra_pai.rrule is None:
        raise HTTPException(status_code=404, detail="Regra de agendamento não encontrada")

    data_excecao_str = update.data_ocorrencia.isoformat()
    if regra_pai.exdates:
        if data_excecao_str not in regra_pai.exdates:
            regra_pai.exdates += f",{data_excecao_str}"
    else:
        regra_pai.exdates = data_excecao_str

    db.commit()

    duracao = regra_pai.data_hora_fim - regra_pai.data_hora_inicio
    novo_agendamento_unico = Agendamento(
        paciente_id=regra_pai.paciente_id,
        data_hora_inicio=update.data_ocorrencia,
        data_hora_fim=update.data_ocorrencia + duracao,
        status=update.novo_status, 
        rrule=None,
        user_id=current_user.id
    )
    db.add(novo_agendamento_unico)
    db.commit()
    db.refresh(novo_agendamento_unico)

    return novo_agendamento_unico


@app.post("/agendamentos/{agendamento_id}/checkin", response_model=AgendamentoSchema)
def fazer_checkin(agendamento_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id, Agendamento.user_id == current_user.id, Agendamento.rrule == None).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento não-recorrente não encontrado")

    db_agendamento.status = 'Presente'
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento

@app.post("/agendamentos/{agendamento_id}/cancelar", response_model=AgendamentoSchema)
def cancelar_atendimento(agendamento_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id, Agendamento.user_id == current_user.id, Agendamento.rrule == None).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento não-recorrente não encontrado")

    db_agendamento.status = 'Cancelado'
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento


# --- Rotas de EVOLUÇÃO ---
@app.post("/agendamentos/{agendamento_id}/evolucoes", status_code=status.HTTP_201_CREATED)
def criar_evolucao(agendamento_id: int, evolucao: EvolucaoCreate, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id, Agendamento.user_id == current_user.id).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento not found")

    if db_agendamento.rrule:
        raise HTTPException(status_code=400, detail="Não é possível adicionar evolução a uma regra. Faça o check-in primeiro.")

    if db_agendamento.evolucao:
        raise HTTPException(status_code=400, detail="Este agendamento já possui uma evolução")

    db_evolucao = Evolucao(
        texto_evolucao=evolucao.texto_evolucao,
        agendamento_id=agendamento_id,
        paciente_id=db_agendamento.paciente_id,
        user_id=current_user.id
    )
    db.add(db_evolucao)
    db.commit()
    return {"detail": "Evolução salva com sucesso"}

@app.get("/pacientes/{paciente_id}/evolucoes", response_model=List[EvolucaoSchema])
def listar_evolucoes_paciente(paciente_id: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id, Paciente.user_id == current_user.id).first()
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente not found")

    evolucoes = db.query(Evolucao).filter(Evolucao.paciente_id == paciente_id).all()
    return evolucoes

# --- Rota de DASHBOARD ---
@app.get("/dashboard/sessoes-por-mes", response_model=List[DashboardSessao])
def get_dashboard_sessoes(ano: int, mes: int, db: Session = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    from sqlalchemy import func, extract

    resultados = db.query(
        Paciente.nome.label("nome_paciente"),
        func.count(Agendamento.id).label("total_sessoes")
    ).join(
        Paciente, Agendamento.paciente_id == Paciente.id
    ).filter(
        Agendamento.status == 'Presente',
        Agendamento.user_id == current_user.id,
        extract('year', Agendamento.data_hora_inicio) == ano,
        extract('month', Agendamento.data_hora_fim) == mes
    ).group_by(
        Paciente.nome
    ).order_by(
        func.count(Agendamento.id).desc()
    ).all()

    return resultados

# --- Rota Raiz (Opcional) ---

@app.get("/")
def read_root():
    return {"message": "API da Agenda de Fisioterapia está no ar!"}