# schemas.py (ATUALIZADO)

from pydantic import BaseModel, computed_field
from datetime import date, datetime
from typing import List, Optional
from enum import Enum

# --- Enums (gênero e status) ---
class Sexo(str, Enum):
    masculino = "Masculino"
    feminino = "Feminino"
    outro = "Outro"

class StatusAgendamento(str, Enum):
    agendado = "Agendado"
    presente = "Presente"
    cancelado = "Cancelado"
    faltou = "Faltou"

# --- Paciente ---
class PacienteBase(BaseModel):
    nome: str
    telefone: str
    data_nascimento: date
    sexo: Sexo
    diagnostico_medico: Optional[str] = None

class PacienteCreate(PacienteBase):
    pass

class Paciente(PacienteBase):
    id: int
    
    class Config:
        from_attributes = True

    @computed_field
    @property
    def idade(self) -> int:
        hoje = date.today()
        nasc = self.data_nascimento
        aniversario_ja_passou = (hoje.month, hoje.day) >= (nasc.month, nasc.day)
        idade_calculada = hoje.year - nasc.year
        if not aniversario_ja_passou:
             idade_calculada -= 1
        return idade_calculada

# --- Agendamento ---
class AgendamentoBase(BaseModel):
    paciente_id: int
    data_hora_inicio: datetime
    data_hora_fim: datetime

class AgendamentoCreate(AgendamentoBase):
    status: StatusAgendamento = StatusAgendamento.agendado

class Agendamento(AgendamentoBase):
    id: int
    status: StatusAgendamento
    
    # --- MUDANÇA PRINCIPAL ---
    # Agora incluímos o objeto completo do paciente na resposta
    paciente: Paciente  

    class Config:
        from_attributes = True

# --- Evolução ---
class EvolucaoBase(BaseModel):
    texto_evolucao: str

class EvolucaoCreate(EvolucaoBase):
    pass

class Evolucao(EvolucaoBase):
    id: int
    agendamento_id: int
    data_criacao: datetime

    class Config:
        from_attributes = True