from enum import Enum, unique


@unique
class ThermodeType(Enum):
    CHEPS = 0
    TSA = 1
    Algometer = 2
    Vibratory = 3
    AirTSA = 4
    CoolingUnit = 5
    TSASlave = 6
    DCHEPS = 7
    Undefined = 255

    def __str__(self):
        return str(self.name)


@unique
class TsaModel(Enum):
    Large30x30 = 0
    Small16x16 = 1
    Small5x5 = 2
    Small2x2 = 3
    IntraOral = 4
    GSA = 5
    Fmri_Large30x30 = 6
    Fmri_Small16x16 = 7
    Fmri_Small5x5 = 8
    Fmri_Small2x2 = 9
    Fmri_IntraOral = 10
    Fmri_GSA = 11
    CPM_Hot = 12
    CPM_Cold = 13
    Unknown = 255

    def __str__(self):
        return str(self.name)


@unique
class HealthStatus(Enum):
    Ok = 0
    APosVoltageFailure = 1
    VPVoltageFailure = 2
    VrefVoltageFailure = 4
    MTECCurrentFailure = 8
    RTECCurrentFailure = 16
    MTECVoltageFailure = 32
    RTECVoltageFailure = 64
    PumpCurrentFailure = 128
    WDTSelfTestFailureOffset = 256
    EmergencyButtonStatusOffset = 512
    WaterLevelWarningOffset = 1024
    MFanFailureOffset = 2048
    RFanFailureOffset = 4096
    ICUFanFailureOffset = 8192
    ICUPumpFailureOffset = 16384
    ICUTECFailureOffset = 32768

    def __str__(self):
        return str(self.name)


@unique
class ACKCODE(Enum):
    Ok = 0
    UnsupportedCommand = 1
    WrongCRC = 2
    IllegalParameter = 3
    IllegalState = 4
    ThermodeDisabled = 5
    IllegalCommandSequence = 6
    BufferFull = 7
    NoDataExists = 8
    DataAlreadyExists = 9
    Fail = 10
    WrongFlashAddress = 11
    WrongSize = 12
    Undefined = 255

    def __str__(self):
        return str(self.name)


@unique
class SystemState(Enum):
    SafeMode = 0
    SelfTest = 1
    RestMode = 2
    TestInit = 3
    TestRun = 4
    TestPaused = 5
    Engineering = 6
    FirmwareUpdate = 7
    WritingBlackBox = 8

    def __str__(self):
        return str(self.name)


class DEVICE_TAG(Enum):
    Master = 0
    Slave = 1

    def __str__(self):
        return str(self.name)


@unique
class COMMAND_ID(Enum):
    Undefined = -1
    ProtocolError = 0
    SetActiveThermode = 18
    GetActiveThermode = 19
    RunTest = 22
    EndTest = 25
    ClearCommandBuffer = 27
    FiniteRampByTime = 28
    FiniteRampByTemperature = 29
    InfiniteRamp = 30
    GetStatusTCU = 33
    GetErrors = 35
    EraseErrors = 36
    GetVersion = 37
    SetTcuState = 41
    SimulateResponseUnit = 45
    StopTest = 47
    GetCurrentPID = 70
    EnableThermode = 83
    GetThermodeState = 84
    FiniteRampByRate = 85

    def __str__(self):
        return str(self.name)


class DeviceType(Enum):
    Undefined = 0
    TCU = 1
    CTS = 2
    Algometer = 3
    TSA2 = 4
    CTSA = 5
    VSA3000 = 6
    CPM = 7
    TSA3 = 8
    TSA3Air = 9

    def __str__(self):
        return str(self.name)


class TcuErrorCode(Enum):
    Ok = 0
    Error_Overheat = 0x8001
    Error_Heat_Duration = 0x8002
    ErrorStaticSensorMismatch = 0x8003
    Error_Dynamic_Sensor_Mismatch = 0x8004
    ErrorEmgDisconnectFail = 0x8005
    ErrorNoHeaterResponse = 0x8006
    Error_No_Tec_Response = 0x8007
    Error_Water_Overheat = 0x8008
    Error_Heater_Sensor = 0x8009
    Error_Tec_Sensor = 0x800A
    Error_Water_Sensor = 0x800B
    Error_Communication_Lost = 0x800C
    Error_No_Enabled_Thermodes = 0x800D
    Error_Cold_Duration = 0x800E
    ErrorChepsThermodeMissing = 0x800F
    ErrorAtsThermodeMissing = 0x8010
    Error_Illegal_State = 0x8011
    ErrorFatalSensorMismatch = 0x8012
    ErrorDurationTable = 0x8013
    ErrorHSDeltaTooBig = 0x8015
    ErrorRateTooBig = 0x8016
    ErrorHS1RateTooBig = 0x8017
    ErrorHS2RateTooBig = 0x8018
    ErrorExternalEmergency = 0x8019
    SafetyTempError = 0x8020
    APIDTempError = 0x8021
    FirmwareInternalError = 0x8080
    Error_Empty_Command_Buffer = 0x400C
    Error_Time_Mark_Missed = 0x400D
    Warning_Sample_Buffer_Full = 0x2001
    Warning_Finite_Ramp_By_Temp_Timeout = 0x2002
    Warning_Static_Sensor_Mismatch = 0x2003
    Warning_Watchdog_Reset = 0x2004
    Warning_Thermode_Disconnected = 0x2005
    Info_Startup = 0x2006
    ErrorWarningSensorMismatch = 0x2007
    ErrorWarningThermodeModelMismatch = 0x2008

    def __str__(self):
        return str(self.name)
