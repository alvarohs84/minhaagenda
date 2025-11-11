from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload # Importe o joinedload
from typing import List
from datetime import datetime

# Import para o CORS
from fastapi.middleware.cors import CORSMiddleware

# Importa tudo dos nossos arquivos (sem o ponto)
import models, schemas
from database import engine, get_db

# Esta linha CRIA as tabelas no seu banco de dados
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="API de Agenda de Fisioterapia",
    version="1.0.0"
)

# Configuração do CORS
origins = [
    "http://localhost",
    "http://127.0.0.1",
    "null",
    "https://alvarohs84.github.io"  # <-- ADICIONE ESTA LINHA
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos os métodos (GET, POST, etc)
    allow_headers=["*"], # Permite todos os cabeçalhos
)

# ===============================================
# FUNÇÕES AUXILIARES (Helpers)
# ===============================================

def get_paciente_by_id(db: Session, paciente_id: int):
    """ Busca um paciente no banco de dados pelo ID. """
    return db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()

def get_agendamento_by_id(db: Session, agendamento_id: int):
    """ Busca um agendamento no banco de dados pelo ID. """
    return db.query(models.Agendamento).filter(models.Agendamento.id == agendamento_id).first()

# ===============================================
# ENDPOINTS DE PACIENTES
# ===============================================

@app.get("/")
def ler_raiz():
    return {"mensagem": "Bem-vindo à API da Agenda de Fisioterapia!"}

@app.post("/pacientes", response_model=schemas.Paciente, status_code=201)
def criar_paciente(paciente: schemas.PacienteCreate, db: Session = Depends(get_db)):
    """
    Cadastra um novo paciente no sistema.
    """
    db_paciente = models.Paciente(**paciente.model_dump())
    db.add(db_paciente)
    db.commit()
    db.refresh(db_paciente) 
    return db_paciente

@app.get("/pacientes", response_model=List[schemas.Paciente])
def listar_pacientes(db: Session = Depends(get_db)):
    """
    Retorna uma lista de todos os pacientes cadastrados.
    """
    pacientes = db.query(models.Paciente).all()
    return pacientes

# ===============================================
# ENDPOINTS DE AGENDAMENTO
# ===============================================

@app.post("/agendamentos", response_model=schemas.Agendamento, status_code=201)
def criar_agendamento(agendamento: schemas.AgendamentoCreate, db: Session = Depends(get_db)):
    """
    Cria um novo agendamento para um paciente.
    """
    paciente = get_paciente_by_id(db, agendamento.paciente_id)
    if not paciente:
        raise HTTPException(
            status_code=404, 
            detail=f"Paciente com ID {agendamento.paciente_id} não encontrado."
        )
        
    db_agendamento = models.Agendamento(**agendamento.model_dump())
    db.add(db_agendamento)
    db.commit()
    db.refresh(db_agendamento)
    return db_agendamento

@app.get("/agendamentos", response_model=List[schemas.Agendamento])
def listar_agendamentos(db: Session = Depends(get_db)):
    """
    Retorna uma lista de todos os agendamentos,
    incluindo os dados do paciente associado.
    """
    # ATUALIZADO: Usamos .options(joinedload(...)) para forçar o JOIN
    # e carregar os dados do paciente imediatamente.
    agendamentos = db.query(models.Agendamento).options(
        joinedload(models.Agendamento.paciente)
    ).all()
    
    return agendamentos

@app.post("/agendamentos/{agendamento_id}/checkin", response_model=schemas.Agendamento)
def fazer_checkin_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    """
    Realiza o check-in de um agendamento, mudando seu status para 'Presente'.
    """
    agendamento = get_agendamento_by_id(db, agendamento_id)
    
    if not agendamento:
        raise HTTPException(
            status_code=404,
            detail=f"Agendamento com ID {agendamento_id} não encontrado."
        )
            
    if agendamento.status == schemas.StatusAgendamento.presente:
        raise HTTPException(
            status_code=400,
            detail="Check-in já realizado para este agendamento."
        )

    agendamento.status = schemas.StatusAgendamento.presente
    
    db.commit()
    db.refresh(agendamento)
    return agendamento

# ===============================================
# ENDPOINTS DE EVOLUÇÃO
# ===============================================

@app.post("/agendamentos/{agendamento_id}/evolucoes", response_model=schemas.Evolucao, status_code=201)
def criar_evolucao(agendamento_id: int, evolucao: schemas.EvolucaoCreate, db: Session = Depends(get_db)):
    """
    Cria uma nova nota de evolução para um agendamento específico.
    """
    agendamento = get_agendamento_by_id(db, agendamento_id)
    if not agendamento:
        raise HTTPException(
            status_code=404,
            detail=f"Agendamento com ID {agendamento_id} não encontrado."
        )
        
    db_evolucao = models.Evolucao(
        agendamento_id=agendamento_id,
        data_criacao=datetime.now(),
        **evolucao.model_dump()
    )
    
    db.add(db_evolucao)
    db.commit()
    db.refresh(db_evolucao)
    return db_evolucao

@app.get("/agendamentos/{agendamento_id}/evolucoes", response_model=List[schemas.Evolucao])
def listar_evolucoes_do_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    """
    Lista todas as notas de evolução de um agendamento específico.
    """
    agendamento = get_agendamento_by_id(db, agendamento_id)
    if not agendamento:
        raise HTTPException(
            status_code=404,
            detail=f"Agendamento com ID {agendamento_id} não encontrado."
        )
        
    return agendamento.evolucoes