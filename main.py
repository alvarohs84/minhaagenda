# --- main.py ---
# [CORRIGIDO] Lógica de atualização (PATCH) da rota de agendamentos

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, Text, Enum as PyEnum
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.orm import declarative_base 
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime, date

# --- 1. CONFIGURAÇÃO DO BANCO DE DADOS ---

# IMPORTANTE: Substitua pela URL do seu banco de dados do Render
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
# Exemplo para PostgreSQL (comum no Render):
# SQLALCHEMY_DATABASE_URL = "postgresql://user:password@host/dbname"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- 2. MODELS (Definição das Tabelas do Banco) ---

class Paciente(Base):
    __tablename__ = 'pacientes'
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=False)
    telefone = Column(String, nullable=True)
    data_nascimento = Column(DateTime, nullable=True) 
    sexo = Column(String, nullable=True)
    diagnostico_medico = Column(String, nullable=True)
    
    agendamentos = relationship("Agendamento", back_populates="paciente", cascade="all, delete-orphan")
    evolucoes = relationship("Evolucao", back_populates="paciente", cascade="all, delete-orphan")

class Agendamento(Base):
    __tablename__ = 'agendamentos'
    id = Column(Integer, primary_key=True, index=True)
    data_hora_inicio = Column(DateTime, nullable=False)
    data_hora_fim = Column(DateTime, nullable=False)
    status = Column(PyEnum('Agendado', 'Presente', 'Cancelado', name='status_agendamento'), default='Agendado')
    
    paciente_id = Column(Integer, ForeignKey('pacientes.id', ondelete="CASCADE"), nullable=False)
    
    paciente = relationship("Paciente", back_populates="agendamentos")
    evolucao = relationship("Evolucao", uselist=False, back_populates="agendamento", cascade="all, delete-orphan")

class Evolucao(Base):
    __tablename__ = 'evolucoes'
    id = Column(Integer, primary_key=True, index=True)
    texto_evolucao = Column(Text, nullable=False)
    data_criacao = Column(DateTime, default=datetime.utcnow)
    
    agendamento_id = Column(Integer, ForeignKey('agendamentos.id'), nullable=False)
    paciente_id = Column(Integer, ForeignKey('pacientes.id'), nullable=False)
    
    agendamento = relationship("Agendamento", back_populates="evolucao")
    paciente = relationship("Paciente", back_populates="evolucoes")

# Cria as tabelas no banco de dados
Base.metadata.create_all(bind=engine)

# --- 3. SCHEMAS (Pydantic - Validação de dados da API) ---

class PacienteBase(BaseModel):
    nome: str
    telefone: Optional[str] = None
    data_nascimento: Optional[date] = None
    sexo: Optional[str] = None
    diagnostico_medico: Optional[str] = None

class PacienteCreate(PacienteBase):
    pass

class PacienteSchema(PacienteBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

class EvolucaoCreate(BaseModel):
    texto_evolucao: str

class AgendamentoCreate(BaseModel):
    paciente_id: int
    data_hora_inicio: datetime
    data_hora_fim: datetime

class AgendamentoUpdate(BaseModel):
    data_hora_inicio: datetime
    data_hora_fim: datetime

class AgendamentoSchema(BaseModel):
    id: int
    data_hora_inicio: datetime
    data_hora_fim: datetime
    status: str
    paciente: PacienteSchema 
    model_config = ConfigDict(from_attributes=True)

class DashboardSessao(BaseModel):
    nome_paciente: str
    total_sessoes: int

class EvolucaoSchema(BaseModel):
    id: int
    texto_evolucao: str
    data_criacao: datetime
    model_config = ConfigDict(from_attributes=True)

# --- 4. INICIALIZAÇÃO DO APP E CORS ---

app = FastAPI(title="Minha Agenda API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],
)

# --- 5. DEPENDÊNCIAS ---

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 6. ROTAS (Endpoints da API) ---

# --- Rotas de PACIENTE ---

@app.post("/pacientes", response_model=PacienteSchema, status_code=status.HTTP_201_CREATED)
def criar_paciente(paciente: PacienteCreate, db: Session = Depends(get_db)):
    data_nasc = datetime.combine(paciente.data_nascimento, datetime.min.time()) if paciente.data_nascimento else None
    
    db_paciente = Paciente(
        nome=paciente.nome,
        telefone=paciente.telefone,
        data_nascimento=data_nasc,
        sexo=paciente.sexo,
        diagnostico_medico=paciente.diagnostico_medico
    )
    db.add(db_paciente)
    db.commit()
    db.refresh(db_paciente)
    return db_paciente

@app.get("/pacientes", response_model=List[PacienteSchema])
def listar_pacientes(db: Session = Depends(get_db)):
    pacientes = db.query(Paciente).all()
    return pacientes

@app.patch("/pacientes/{paciente_id}", response_model=PacienteSchema)
def atualizar_paciente(paciente_id: int, paciente: PacienteCreate, db: Session = Depends(get_db)):
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
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
def deletar_paciente(paciente_id: int, db: Session = Depends(get_db)):
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
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
def listar_agendamentos(db: Session = Depends(get_db)):
    agendamentos = db.query(Agendamento).all()
    return agendamentos

@app.post("/agendamentos", response_model=AgendamentoSchema, status_code=status.HTTP_201_CREATED)
def criar_agendamento(agendamento: AgendamentoCreate, db: Session = Depends(get_db)):
    db_paciente = db.query(Paciente).filter(Paciente.id == agendamento.paciente_id).first()
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente not found")
        
    db_agendamento = Agendamento(
        paciente_id=agendamento.paciente_id,
        data_hora_inicio=agendamento.data_hora_inicio,
        data_hora_fim=agendamento.data_hora_fim,
        status='Agendado'
    )
    db.add(db_agendamento)
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento

# [FUNÇÃO CORRIGIDA]
@app.patch("/agendamentos/{agendamento_id}", response_model=AgendamentoSchema)
def atualizar_data_agendamento(agendamento_id: int, update_data: AgendamentoUpdate, db: Session = Depends(get_db)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento not found")
    
    try:
        # Pega os dados enviados (ex: data_hora_inicio e data_hora_fim)
        update_data_dict = update_data.model_dump(exclude_unset=True)
        
        # Atualiza os campos no objeto do banco de dados
        for key, value in update_data_dict.items():
            setattr(db_agendamento, key, value)
            
        db.commit() # Salva as mudanças
        db.refresh(db_agendamento)
        return db_agendamento
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar no banco: {e}")

@app.delete("/agendamentos/{agendamento_id}", status_code=status.HTTP_200_OK)
def deletar_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento not found")
        
    db.delete(db_agendamento)
    db.commit()
    return {"detail": "Agendamento deletado com sucesso"}

# --- Rotas de AÇÕES (Check-in, Cancelar) ---

@app.post("/agendamentos/{agendamento_id}/checkin", response_model=AgendamentoSchema)
def fazer_checkin(agendamento_id: int, db: Session = Depends(get_db)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento not found")
    
    db_agendamento.status = 'Presente'
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento

@app.post("/agendamentos/{agendamento_id}/cancelar", response_model=AgendamentoSchema)
def cancelar_atendimento(agendamento_id: int, db: Session = Depends(get_db)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento not found")
    
    db_agendamento.status = 'Cancelado'
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento

# --- Rotas de EVOLUÇÃO ---

@app.post("/agendamentos/{agendamento_id}/evolucoes", status_code=status.HTTP_201_CREATED)
def criar_evolucao(agendamento_id: int, evolucao: EvolucaoCreate, db: Session = Depends(get_db)):
    db_agendamento = db.query(Agendamento).filter(Agendamento.id == agendamento_id).first()
    if db_agendamento is None:
        raise HTTPException(status_code=404, detail="Agendamento not found")
    
    if db_agendamento.evolucao:
        raise HTTPException(status_code=400, detail="Este agendamento já possui uma evolução")

    db_evolucao = Evolucao(
        texto_evolucao=evolucao.texto_evolucao,
        agendamento_id=agendamento_id,
        paciente_id=db_agendamento.paciente_id
    )
    db.add(db_evolucao)
    db.commit()
    return {"detail": "Evolução salva com sucesso"}

@app.get("/pacientes/{paciente_id}/evolucoes", response_model=List[EvolucaoSchema])
def listar_evolucoes_paciente(paciente_id: int, db: Session = Depends(get_db)):
    db_paciente = db.query(Paciente).filter(Paciente.id == paciente_id).first()
    if db_paciente is None:
        raise HTTPException(status_code=404, detail="Paciente not found")
        
    evolucoes = db.query(Evolucao).filter(Evolucao.paciente_id == paciente_id).all()
    return evolucoes

# --- Rota de DASHBOARD ---

@app.get("/dashboard/sessoes-por-mes", response_model=List[DashboardSessao])
def get_dashboard_sessoes(ano: int, mes: int, db: Session = Depends(get_db)):
    from sqlalchemy import func, extract
    
    resultados = db.query(
        Paciente.nome.label("nome_paciente"),
        func.count(Agendamento.id).label("total_sessoes")
    ).join(
        Paciente, Agendamento.paciente_id == Paciente.id
    ).filter(
        Agendamento.status == 'Presente',
        extract('year', Agendamento.data_hora_inicio) == ano,
        extract('month', Agendamento.data_hora_inicio) == mes
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