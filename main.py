from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, extract
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
    "https://alvarohs84.github.io"  # URL do seu frontend no GitHub Pages
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos os métodos
    allow_headers=["*"], # Permite todos os cabeçalhos
)

# ===============================================
# FUNÇÕES AUXILIARES (Helpers)
# ===============================================

def get_paciente_by_id(db: Session, paciente_id: int):
    """ Busca um paciente no banco de dados pelo ID. """
    return db.query(models.Paciente).filter(models.Paciente.id == paciente_id).first()

def get_agendamento_by_id(db: Session, agendamento_id: int):
    """ 
    Busca um agendamento no banco de dados pelo ID,
    já incluindo (joinedload) os dados do paciente.
    """
    return db.query(models.Agendamento).options(
        joinedload(models.Agendamento.paciente)
    ).filter(models.Agendamento.id == agendamento_id).first()

# ===============================================
# ENDPOINTS DE PACIENTES
# ===============================================

@app.get("/")
def ler_raiz():
    return {"mensagem": "Bem-vindo à API da Agenda de Fisioterapia!"}

@app.post("/pacientes", response_model=schemas.Paciente, status_code=201)
def criar_paciente(paciente: schemas.PacienteCreate, db: Session = Depends(get_db)):
    db_paciente = models.Paciente(**paciente.model_dump())
    db.add(db_paciente)
    db.commit()
    db.refresh(db_paciente) 
    return db_paciente

@app.get("/pacientes", response_model=List[schemas.Paciente])
def listar_pacientes(db: Session = Depends(get_db)):
    pacientes = db.query(models.Paciente).all()
    return pacientes

# ===============================================
# ENDPOINTS DE AGENDAMENTO
# ===============================================

@app.post("/agendamentos", response_model=schemas.Agendamento, status_code=201)
def criar_agendamento(agendamento: schemas.AgendamentoCreate, db: Session = Depends(get_db)):
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
    agendamentos = db.query(models.Agendamento).options(
        joinedload(models.Agendamento.paciente)
    ).all()
    return agendamentos

@app.patch("/agendamentos/{agendamento_id}", response_model=schemas.Agendamento)
def atualizar_agendamento(
    agendamento_id: int, 
    agendamento_update: schemas.AgendamentoUpdate, 
    db: Session = Depends(get_db)
):
    """
    Atualiza um agendamento (ex: muda data/hora).
    Usado pelo drag-and-drop.
    """
    db_agendamento = get_agendamento_by_id(db, agendamento_id)
    if not db_agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    update_data = agendamento_update.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_agendamento, key, value)
        
    db.commit()
    db.refresh(db_agendamento)
    
    return db_agendamento

@app.post("/agendamentos/{agendamento_id}/checkin", response_model=schemas.Agendamento)
def fazer_checkin_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    agendamento = get_agendamento_by_id(db, agendamento_id)
    if not agendamento:
        raise HTTPException(status_code=404, detail=f"Agendamento com ID {agendamento_id} não encontrado.")
    if agendamento.status == schemas.StatusAgendamento.presente:
        raise HTTPException(status_code=400, detail="Check-in já realizado para este agendamento.")
    agendamento.status = schemas.StatusAgendamento.presente
    db.commit()
    db.refresh(agendamento)
    return agendamento

@app.post("/agendamentos/{agendamento_id}/cancelar", response_model=schemas.Agendamento)
def cancelar_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    agendamento = get_agendamento_by_id(db, agendamento_id)
    if not agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    if agendamento.status == schemas.StatusAgendamento.presente:
        raise HTTPException(status_code=400, detail="Não é possível cancelar um agendamento que já ocorreu.")
    if agendamento.status == schemas.StatusAgendamento.cancelado:
        return agendamento
    agendamento.status = schemas.StatusAgendamento.cancelado
    db.commit()
    db.refresh(agendamento)
    return agendamento

# ===============================================
# ENDPOINTS DE EVOLUÇÃO
# ===============================================

@app.post("/agendamentos/{agendamento_id}/evolucoes", response_model=schemas.Evolucao, status_code=201)
def criar_evolucao(agendamento_id: int, evolucao: schemas.EvolucaoCreate, db: Session = Depends(get_db)):
    agendamento = get_agendamento_by_id(db, agendamento_id)
    if not agendamento:
        raise HTTPException(status_code=404, detail=f"Agendamento com ID {agendamento_id} não encontrado.")
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
    agendamento = get_agendamento_by_id(db, agendamento_id)
    if not agendamento:
        raise HTTPException(status_code=404, detail=f"Agendamento com ID {agendamento_id} não encontrado.")
    return agendamento.evolucoes

# ===============================================
# ENDPOINT DE HISTÓRICO DE EVOLUÇÕES
# ===============================================

@app.get("/pacientes/{paciente_id}/evolucoes", response_model=List[schemas.Evolucao])
def get_historico_evolucoes_paciente(paciente_id: int, db: Session = Depends(get_db)):
    """
    Busca todas as evoluções de um paciente específico,
    ordenadas da mais recente para a mais antiga.
    """
    paciente = get_paciente_by_id(db, paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
        
    historico = db.query(models.Evolucao) \
        .join(models.Agendamento, models.Evolucao.agendamento_id == models.Agendamento.id) \
        .filter(models.Agendamento.paciente_id == paciente_id) \
        .order_by(models.Evolucao.data_criacao.desc()) \
        .all()
        
    return historico

# ===============================================
# ENDPOINT DE DASHBOARD
# ===============================================

@app.get("/dashboard/sessoes-por-mes", response_model=List[schemas.SessaoDashboard])
def get_dashboard_sessoes(ano: int, mes: int, db: Session = Depends(get_db)):
    try:
        resultados = db.query(
            models.Paciente.nome.label("nome_paciente"),
            func.count(models.Agendamento.id).label("total_sessoes")
        ).join(models.Paciente, models.Agendamento.paciente_id == models.Paciente.id) \
         .filter(models.Agendamento.status == schemas.StatusAgendamento.presente) \
         .filter(extract('year', models.Agendamento.data_hora_inicio) == ano) \
         .filter(extract('month', models.Agendamento.data_hora_inicio) == mes) \
         .group_by(models.Paciente.nome) \
         .order_by(func.count(models.Agendamento.id).desc()) \
         .all()
        return resultados
    except Exception as e:
        print(f"Erro no dashboard: {e}") 
        raise HTTPException(status_code=500, detail="Erro ao processar a consulta do dashboard.")