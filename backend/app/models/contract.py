"""Contrato (Contract) ORM Model."""
from datetime import datetime, timezone, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.database import Base

class TipologiaContrato(str, enum.Enum):
    PRESTACION_SERVICIOS = "PRESTACION_SERVICIOS"
    OBRA = "OBRA"
    SUMINISTRO = "SUMINISTRO"
    CONSULTORIA = "CONSULTORIA"
    INTERVENTORIA = "INTERVENTORIA"
    ARRENDAMIENTO = "ARRENDAMIENTO"

class ModalidadSeleccion(str, enum.Enum):
    CONTRATACION_DIRECTA = "CONTRATACION_DIRECTA"
    INVITACION_PRIVADA = "INVITACION_PRIVADA"
    INVITACION_PUBLICA = "INVITACION_PUBLICA"
    MINIMA_CUANTIA = "MINIMA_CUANTIA"

class EstadoContrato(str, enum.Enum):
    BORRADOR = "BORRADOR"
    EN_REVISION = "EN_REVISION"
    APROBADO = "APROBADO"
    EN_EJECUCION = "EN_EJECUCION"
    TERMINADO = "TERMINADO"
    SUSPENDIDO = "SUSPENDIDO"
    LIQUIDADO = "LIQUIDADO"
    ANULADO = "ANULADO"

class UnidadPlazo(str, enum.Enum):
    DIAS = "DIAS"
    MESES = "MESES"

class Contrato(Base):
    __tablename__ = "contratos"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    numero_contrato = Column(String(50), unique=True, index=True, nullable=False)
    vigencia = Column(Integer, default=lambda: datetime.now().year, nullable=False)
    modalidad_seleccion = Column(
        SQLEnum(ModalidadSeleccion), 
        default=ModalidadSeleccion.CONTRATACION_DIRECTA, 
        nullable=False
    )
    tipologia = Column(
        SQLEnum(TipologiaContrato), 
        default=TipologiaContrato.PRESTACION_SERVICIOS, 
        nullable=False
    )
    
    # Contratista asociado
    contratista_id = Column(Integer, ForeignKey("contratistas.id"), nullable=False)

    # Componentes redactados / estructurados por Agente o Usuario
    objeto = Column(Text, nullable=False)
    justificacion_necesidad = Column(Text, nullable=True)
    marco_juridico = Column(Text, nullable=True)
    objetivo_general = Column(Text, nullable=True)
    objetivos_especificos = Column(JSON, default=list, nullable=True)
    obligaciones_estudio_previo = Column(JSON, default=list, nullable=True)
    obligaciones_minuta = Column(JSON, default=list, nullable=True)
    obligaciones_empresa = Column(JSON, default=list, nullable=True)

    # Aspectos económicos y de ejecución
    valor_inicial = Column(Float, nullable=True)
    adicion_1 = Column(Float, nullable=True, default=0.0)
    valor_total = Column(Float, nullable=False, default=0.0)
    valor_en_letras = Column(String(255), nullable=True)
    forma_pago = Column(Text, nullable=True)
    plazo_ejecucion = Column(Integer, default=1, nullable=False)
    unidad_plazo = Column(SQLEnum(UnidadPlazo), default=UnidadPlazo.MESES, nullable=False)
    plazo_texto = Column(String(50), nullable=True)  # Ej: '12 meses', '45 días', '8 días'
    prorroga_1 = Column(String(100), nullable=True)
    lugar_ejecucion = Column(String(200), default="Jurisdicción de la ESP", nullable=True)

    # Presupuesto y Disponibilidad
    cdp_numero = Column(String(50), nullable=True)
    cdp_fecha = Column(Date, nullable=True)
    cdp_rubro = Column(String(100), nullable=True)
    rp_numero = Column(String(50), nullable=True)
    rp_fecha = Column(Date, nullable=True)

    # Supervisión e Interventoría
    supervisor_nombre = Column(String(200), nullable=True)
    supervisor_cargo = Column(String(200), nullable=True)
    supervisor_tipo_documento = Column(String(20), default="CC", nullable=True)
    supervisor_documento = Column(String(50), nullable=True)
    supervisor_dependencia = Column(String(200), nullable=True)

    # Fechas del ciclo de vida contractual
    fecha_estudio_previo = Column(Date, default=lambda: date.today(), nullable=True)
    fecha_suscripcion = Column(Date, nullable=True)
    fecha_acta_inicio = Column(Date, nullable=True)
    fecha_terminacion = Column(Date, nullable=True)

    # Estado y garantías
    estado = Column(SQLEnum(EstadoContrato), default=EstadoContrato.BORRADOR, nullable=False)
    motivo_anulacion = Column(Text, nullable=True)
    anulado_por = Column(String(200), nullable=True)
    fecha_anulacion = Column(DateTime, nullable=True)
    garantias_exigidas = Column(JSON, default=dict, nullable=True)
    
    # Metadatos generados por el Agente LLM
    metadatos_agente = Column(JSON, default=dict, nullable=True)

    # Estudio de Mercado (Análisis de precios unitarios APU y Elección de Contratista)
    estudio_mercado = Column(JSON, default=None, nullable=True)

    # Clasificación oficial de códigos UNSPSC (Agente UNSPSC)
    codigos_unspsc = Column(JSON, default=None, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relaciones
    contratista = relationship("Contratista", back_populates="contratos")
    documentos = relationship("Documento", back_populates="contrato", cascade="all, delete-orphan")
    auditorias = relationship("Auditoria", back_populates="contrato")
    adiciones = relationship("AdicionContrato", back_populates="contrato", cascade="all, delete-orphan")
    pagos = relationship("PagoContrato", back_populates="contrato", cascade="all, delete-orphan")

