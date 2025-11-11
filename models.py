from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime # <-- ADICIONE ESTA LINHA

# Importa o 'Base' do database.py (sem o ponto)
from database import Base 

# Importa os Enums do schemas.py (sem o ponto)
from schemas import Sexo, StatusAgendamento

class Paciente(Base):
    __tablename__ = "pacientes" # Nome da tabela no PostgreSQL

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True)
    telefone = Column(String)
    data_nascimento = Column(Date)
    sexo = Column(Enum(Sexo))
    diagnostico_medico = Column(String, nullable=True)

    # Relacionamento: Um paciente pode ter muitos agendamentos
    agendamentos = relationship("Agendamento", back_populates="paciente")

class Agendamento(Base):
    __tablename__ = "agendamentos"

    id = Column(Integer, primary_key=True, index=True)
    data_hora_inicio = Column(DateTime)
    data_hora_fim = Column(DateTime)
    status = Column(Enum(StatusAgendamento), default=StatusAgendamento.agendado)
    
    paciente_id = Column(Integer, ForeignKey("pacientes.id"))

    # Relacionamento: Um agendamento pertence a um paciente
    paciente = relationship("Paciente", back_populates="agendamentos")
    
    # Relacionamento: Um agendamento pode ter muitas evoluções
    evolucoes = relationship("Evolucao", back_populates="agendamento")

class Evolucao(Base):
    __tablename__ = "evolucoes"

    id = Column(Integer, primary_key=True, index=True)
    texto_evolucao = Column(String)
    
    # AQUI ESTAVA O ERRO: agora o 'datetime.now' é reconhecido
    data_criacao = Column(DateTime, default=datetime.now) 
    
    agendamento_id = Column(Integer, ForeignKey("agendamentos.id"))

    # Relacionamento: Uma evolução pertence a um agendamento
    agendamento = relationship("Agendamento", back_populates="evolucoes")