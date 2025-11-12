from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime

# Importa o 'Base' do database.py (sem o ponto)
from database import Base 

# Importa os Enums do schemas.py (sem o ponto)
from schemas import Sexo, StatusAgendamento

class Paciente(Base):
    __tablename__ = "pacientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    telefone = Column(String)
    data_nascimento = Column(Date)
    sexo = Column(Enum(Sexo))
    diagnostico_medico = Column(String, nullable=True)

    agendamentos = relationship("Agendamento", back_populates="paciente")

class Agendamento(Base):
    __tablename__ = "agendamentos"

    id = Column(Integer, primary_key=True, index=True)
    data_hora_inicio = Column(DateTime)
    data_hora_fim = Column(DateTime)
    status = Column(Enum(StatusAgendamento), default=StatusAgendamento.agendado)
    
    paciente_id = Column(Integer, ForeignKey("pacientes.id", ondelete="CASCADE"))

    paciente = relationship("Paciente", back_populates="agendamentos")
    evolucoes = relationship("Evolucao", back_populates="agendamento")

class Evolucao(Base):
    __tablename__ = "evolucoes"

    id = Column(Integer, primary_key=True, index=True)
    texto_evolucao = Column(String)
    data_criacao = Column(DateTime, default=datetime.now) 
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id"))

    agendamento = relationship("Agendamento", back_populates="evolucoes")