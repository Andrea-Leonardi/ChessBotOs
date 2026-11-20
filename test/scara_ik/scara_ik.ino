// Controllo cinematico inverso (IK) per Double Arm SCARA + Asse Z (ChessBot) su ESP32
// Porting di test/InverseKinematic/IK.py con input da Serial Monitor (115200 baud)
//
// Cablaggio motori:
//   mot_L -> DIR: G19, STEP: G18 (1/16, riduzione 16T->100T = 6.25)
//   mot_R -> DIR: G25, STEP: G32 (1/16, riduzione 16T->100T = 6.25)
//   mot_Z -> DIR: G17, STEP: G5  (1/4,  riduzione 1:3 su vite trapezoidale T8)
//
// Comandi supportati da Serial Monitor:
//   - Casella scacchiera: a1 .. h8 (es. a8, e4, h1)
//   - Posizioni speciali: home (0, 0), cemetery (176, 179.4)
//   - Coordinate dirette: x,y (es. 0,0 oppure -32.5,140)
//   - Asse Z relativo:    z+10 (sale di 10 mm), z-10 (scende di 10 mm)
//   - Asse Z assoluto:    z0, z20 (porta Z a quota assoluta rispetto allo zero iniziale)
//   - Stato attuale:      pos oppure ?

#include <Arduino.h>
#include <math.h>

// ---------------- Pin e parametri motori ----------------
constexpr int DIR_PIN_L  = 19;
constexpr int STEP_PIN_L = 18;
constexpr int DIR_PIN_R  = 25;
constexpr int STEP_PIN_R = 32;
constexpr int DIR_PIN_Z  = 17;
constexpr int STEP_PIN_Z = 5;

constexpr int FULL_STEPS_PER_REV = 200; // 17HS19: 1.8 gradi/step
constexpr int MICROSTEPPING_L    = 16;
constexpr int MICROSTEPPING_R    = 16;
constexpr int MICROSTEPPING_Z    = 4;

// Rapporti di riduzione meccanici
// L/R: nominale 16T->100T (6.25), calibrato su 35 punti misurati = 6.51 (RMS ~1.6 mm)
constexpr double GEAR_RATIO_L = 6.51;
constexpr double GEAR_RATIO_R = 6.51;
// Z: riduzione 1:3 (3 giri motore = 1 giro vite) su vite trapezoidale T8
constexpr double GEAR_RATIO_Z = 3.0;
// Passo (lead) della vite T8 in mm per giro completo della vite:
// T8x8 (4 principi, standard stampanti 3D) = 8.0 mm/giro (se T8x2 metti 2.0, se T8x4 metti 4.0)
constexpr double LEAD_Z_MM    = 8.0;

// Impostare a true se il senso positivo del motore è invertito sul cablaggio fisico
constexpr bool INVERT_DIR_L = true;
constexpr bool INVERT_DIR_R = false;
constexpr bool INVERT_DIR_Z = false; // Se z+10 scende invece di salire, imposta true

constexpr double STEPS_PER_DEG_L =
    (static_cast<double>(FULL_STEPS_PER_REV) * MICROSTEPPING_L * GEAR_RATIO_L) / 360.0;
constexpr double STEPS_PER_DEG_R =
    (static_cast<double>(FULL_STEPS_PER_REV) * MICROSTEPPING_R * GEAR_RATIO_R) / 360.0;
constexpr double STEPS_PER_MM_Z =
    (static_cast<double>(FULL_STEPS_PER_REV) * MICROSTEPPING_Z * GEAR_RATIO_Z) / LEAD_Z_MM;

// Temporizzazione step coordinati L/R
constexpr long STEP_PULSE_US = 3;    // A4988 >= 1 us
constexpr long MIN_FREQ_HZ   = 800;  // Frequenza iniziale/finale rampa L/R
constexpr long MAX_FREQ_HZ   = 3500; // Frequenza di crociera L/R (step/s)
constexpr long RAMP_STEPS    = 400;  // Passi di accelerazione/decelerazione L/R

// Temporizzazione step asse Z (1/4 microstepping)
constexpr long STEP_PULSE_Z_US = 2;
constexpr long MIN_FREQ_Z_HZ   = 500;
constexpr long MAX_FREQ_Z_HZ   = 4500;
constexpr long RAMP_STEPS_Z    = 600;

// ---------------- Geometria SCARA (da IK.py) ----------------
constexpr double ORIGIN_L_X = -45.0;
constexpr double ORIGIN_L_Y = -92.1;
constexpr double ORIGIN_R_X =  45.0;
constexpr double ORIGIN_R_Y = -92.1;
constexpr double ARM_A      = 183.0;
constexpr double ARM_B      = 230.0;

// Parametri scacchiera (8 caselle reali = 254 mm -> 31.75 mm/casella, centro d1/e1 a Y = 51.4 mm)
constexpr double SQUARE_SIZE_MM = 254.0 / 8.0;
constexpr double ROW1_CENTER_Y  = 51.4;

// Offset della scacchiera rispetto a home (0, 0) in mm:
// +X = più a destra, +Y = più avanti
constexpr double BOARD_OFFSET_X = 0.0;
constexpr double BOARD_OFFSET_Y = 0.0;

// Correzione angolare di azzeramento home (da calibrazione su 35 punti: dL = -1.55 deg, dR = +0.37 deg)
constexpr double HOME_ANGLE_OFFSET_L = -1.55;
constexpr double HOME_ANGLE_OFFSET_R =  0.37;

// Compensazione automatica caduta (flessione) bracci lungo Y tramite asse Z:
// Da riga 1 (a1) a riga 8 (a8) la testa scende di 3.0 mm -> Z sale linearmente con Y
constexpr double Z_DROOP_MM_A1_TO_A8   = 3.0;
constexpr double Z_COMP_SLOPE_PER_MM_Y = Z_DROOP_MM_A1_TO_A8 / (7.0 * SQUARE_SIZE_MM);

constexpr double RAD_TO_DEG_VAL = 180.0 / PI;

// Stato corrente: all'avvio si assume il braccio in home (0, 0) e Z = 0 mm
double homeAngleL    = 0.0;
double homeAngleR    = 0.0;
double currentX      = 0.0;
double currentY      = 0.0;
double currentZMm    = 0.0; // Quota logica Z impostata dall'utente (al netto della compensazione Y)
double currentAngleL = 0.0;
double currentAngleR = 0.0;
long currentStepsL   = 0; // Step relativi alla posizione home (0,0)
long currentStepsR   = 0;
long currentStepsZ   = 0; // Step fisici Z relativi a home (0,0) con Z = 0 mm

double zCompensationMm(double yMm) {
  return (yMm > 0.0) ? (yMm * Z_COMP_SLOPE_PER_MM_Y) : 0.0;
}

double clampUnit(double v) {
  if (v > 1.0) return 1.0;
  if (v < -1.0) return -1.0;
  return v;
}

bool computeIK(double targetX, double targetY, double& outAngleL, double& outAngleR, String& errMsg) {
  const double dxL = targetX - ORIGIN_L_X;
  const double dyL = targetY - ORIGIN_L_Y;
  const double dxR = targetX - ORIGIN_R_X;
  const double dyR = targetY - ORIGIN_R_Y;

  const double cL = sqrt(dxL * dxL + dyL * dyL);
  const double cR = sqrt(dxR * dxR + dyR * dyR);

  const double minReach = fabs(ARM_A - ARM_B);
  const double maxReach = ARM_A + ARM_B;

  if (cL < minReach || cL > maxReach) {
    errMsg = "Target fuori portata per il braccio sinistro (mot_L)";
    return false;
  }
  if (cR < minReach || cR > maxReach) {
    errMsg = "Target fuori portata per il braccio destro (mot_R)";
    return false;
  }

  const double cosAlphaL = clampUnit((ARM_A * ARM_A + cL * cL - ARM_B * ARM_B) / (2.0 * ARM_A * cL));
  const double cosAlphaR = clampUnit((ARM_A * ARM_A + cR * cR - ARM_B * ARM_B) / (2.0 * ARM_A * cR));

  const double alphaL = acos(cosAlphaL) * RAD_TO_DEG_VAL;
  const double alphaR = acos(cosAlphaR) * RAD_TO_DEG_VAL;

  const double h = -ORIGIN_L_Y + targetY;
  const double betaL = acos(clampUnit(h / cL)) * RAD_TO_DEG_VAL;
  const double betaR = acos(clampUnit(h / cR)) * RAD_TO_DEG_VAL;

  const double posRelL = targetX - ORIGIN_L_X;
  const double posRelR = targetX - ORIGIN_R_X;

  outAngleL = (posRelL > 0.0) ? -(alphaL - betaL) : -(alphaL + betaL);
  outAngleR = (posRelR > 0.0) ? (alphaR + betaR) : (alphaR - betaR);
  return true;
}

void moveMotorsSimultaneous(long deltaStepsL, long deltaStepsR) {
  const long stepsL = labs(deltaStepsL);
  const long stepsR = labs(deltaStepsR);
  const long totalTicks = max(stepsL, stepsR);

  if (totalTicks == 0) {
    return;
  }

  bool dirHighL = (deltaStepsL >= 0);
  bool dirHighR = (deltaStepsR >= 0);
  if (INVERT_DIR_L) dirHighL = !dirHighL;
  if (INVERT_DIR_R) dirHighR = !dirHighR;

  digitalWrite(DIR_PIN_L, dirHighL ? HIGH : LOW);
  digitalWrite(DIR_PIN_R, dirHighR ? HIGH : LOW);
  delayMicroseconds(10); // Setup time DIR prima del fronte STEP

  const long ramp = min(RAMP_STEPS, totalTicks / 2);
  const long startFreq = min(MIN_FREQ_HZ, MAX_FREQ_HZ);
  const long freqSpan = MAX_FREQ_HZ - startFreq;

  long errL = 0;
  long errR = 0;

  // Interpolazione coordinata a 2 assi (Bresenham) per L e R
  for (long i = 0; i < totalTicks; i++) {
    long freqHz = MAX_FREQ_HZ;
    if (ramp > 0 && freqSpan > 0) {
      if (i < ramp) {
        freqHz = startFreq + (freqSpan * i) / ramp;
      } else if (i >= totalTicks - ramp) {
        const long remaining = totalTicks - 1 - i;
        freqHz = startFreq + (freqSpan * remaining) / ramp;
      }
    }

    bool stepL = false;
    bool stepR = false;

    errL += stepsL;
    if (errL >= totalTicks) {
      errL -= totalTicks;
      stepL = true;
    }

    errR += stepsR;
    if (errR >= totalTicks) {
      errR -= totalTicks;
      stepR = true;
    }

    if (stepL) digitalWrite(STEP_PIN_L, HIGH);
    if (stepR) digitalWrite(STEP_PIN_R, HIGH);
    delayMicroseconds(STEP_PULSE_US);
    if (stepL) digitalWrite(STEP_PIN_L, LOW);
    if (stepR) digitalWrite(STEP_PIN_R, LOW);

    const long stepPeriodUs = 1000000L / freqHz;
    const long lowDelayUs = stepPeriodUs - STEP_PULSE_US;
    if (lowDelayUs > 0) {
      delayMicroseconds(lowDelayUs);
    }
  }
}

void moveMotorZ(long deltaStepsZ) {
  const long stepsZ = labs(deltaStepsZ);
  if (stepsZ == 0) {
    return;
  }

  bool dirHighZ = (deltaStepsZ >= 0);
  if (INVERT_DIR_Z) dirHighZ = !dirHighZ;

  digitalWrite(DIR_PIN_Z, dirHighZ ? HIGH : LOW);
  delayMicroseconds(10);

  const long ramp = min(RAMP_STEPS_Z, stepsZ / 2);
  const long startFreq = min(MIN_FREQ_Z_HZ, MAX_FREQ_Z_HZ);
  const long freqSpan = MAX_FREQ_Z_HZ - startFreq;

  for (long i = 0; i < stepsZ; i++) {
    long freqHz = MAX_FREQ_Z_HZ;
    if (ramp > 0 && freqSpan > 0) {
      if (i < ramp) {
        freqHz = startFreq + (freqSpan * i) / ramp;
      } else if (i >= stepsZ - ramp) {
        const long remaining = stepsZ - 1 - i;
        freqHz = startFreq + (freqSpan * remaining) / ramp;
      }
    }

    digitalWrite(STEP_PIN_Z, HIGH);
    delayMicroseconds(STEP_PULSE_Z_US);
    digitalWrite(STEP_PIN_Z, LOW);

    const long stepPeriodUs = 1000000L / freqHz;
    const long lowDelayUs = stepPeriodUs - STEP_PULSE_Z_US;
    if (lowDelayUs > 0) {
      delayMicroseconds(lowDelayUs);
    }
  }
}

bool parseZCommand(const String& rawCmd, bool& isRelative, double& valueMm) {
  String cmd = rawCmd;
  cmd.trim();
  cmd.toLowerCase();

  if (cmd.length() < 2 || cmd[0] != 'z') {
    return false;
  }

  String arg = cmd.substring(1);
  arg.trim();
  if (arg.length() == 0) {
    return false;
  }

  isRelative = (arg[0] == '+' || arg[0] == '-');

  char* endPtr = nullptr;
  const double parsed = strtod(arg.c_str(), &endPtr);
  if (endPtr == arg.c_str() || *endPtr != '\0') {
    return false;
  }

  valueMm = parsed;
  return true;
}

bool parseCommandToTarget(const String& rawCmd, double& outX, double& outY, String& label) {
  String cmd = rawCmd;
  cmd.trim();
  cmd.toLowerCase();

  if (cmd == "home") {
    outX = 0.0;
    outY = 0.0;
    label = "home";
    return true;
  }

  if (cmd == "cemetery") {
    outX = 176.0 + BOARD_OFFSET_X;
    outY = 179.4 + BOARD_OFFSET_Y;
    label = "cemetery";
    return true;
  }

  // Casella scacchiera: a1 .. h8
  if (cmd.length() == 2 && cmd[0] >= 'a' && cmd[0] <= 'h' && cmd[1] >= '1' && cmd[1] <= '8') {
    const int colIdx = cmd[0] - 'a';
    const int rowIdx = cmd[1] - '1';
    outX = (colIdx - 3.5) * SQUARE_SIZE_MM + BOARD_OFFSET_X;
    outY = (rowIdx * SQUARE_SIZE_MM) + ROW1_CENTER_Y + BOARD_OFFSET_Y;
    label = cmd;
    return true;
  }

  // Coordinate numeriche "x,y"
  const int commaIdx = cmd.indexOf(',');
  if (commaIdx > 0 && commaIdx < static_cast<int>(cmd.length()) - 1) {
    String xStr = cmd.substring(0, commaIdx);
    String yStr = cmd.substring(commaIdx + 1);
    xStr.trim();
    yStr.trim();

    char* endX = nullptr;
    char* endY = nullptr;
    const double xVal = strtod(xStr.c_str(), &endX);
    const double yVal = strtod(yStr.c_str(), &endY);
    if (endX != xStr.c_str() && *endX == '\0' && endY != yStr.c_str() && *endY == '\0') {
      outX = xVal;
      outY = yVal;
      label = "(" + String(outX, 1) + ", " + String(outY, 1) + ")";
      return true;
    }
  }

  return false;
}

void printStatus() {
  const double compZ = zCompensationMm(currentY);
  Serial.printf("Posizione -> XY: (%.2f, %.2f) mm | Z: %.2f mm (comp %+.2f mm, %ld step) | Angoli L/R: (%.2f, %.2f) deg | Step L/R: (%ld, %ld)\n",
                currentX, currentY, currentZMm, compZ, currentStepsZ,
                currentAngleL, currentAngleR, currentStepsL, currentStepsR);
}

void setup() {
  Serial.begin(115200);

  pinMode(DIR_PIN_L, OUTPUT);
  pinMode(STEP_PIN_L, OUTPUT);
  pinMode(DIR_PIN_R, OUTPUT);
  pinMode(STEP_PIN_R, OUTPUT);
  pinMode(DIR_PIN_Z, OUTPUT);
  pinMode(STEP_PIN_Z, OUTPUT);

  digitalWrite(DIR_PIN_L, LOW);
  digitalWrite(STEP_PIN_L, LOW);
  digitalWrite(DIR_PIN_R, LOW);
  digitalWrite(STEP_PIN_R, LOW);
  digitalWrite(DIR_PIN_Z, LOW);
  digitalWrite(STEP_PIN_Z, LOW);

  String err;
  computeIK(0.0, 0.0, homeAngleL, homeAngleR, err);
  homeAngleL += HOME_ANGLE_OFFSET_L;
  homeAngleR += HOME_ANGLE_OFFSET_R;
  currentX = 0.0;
  currentY = 0.0;
  currentZMm = 0.0;
  currentAngleL = homeAngleL;
  currentAngleR = homeAngleR;
  currentStepsL = 0;
  currentStepsR = 0;
  currentStepsZ = 0;

  delay(500);
  Serial.println("=== SCARA ChessBot IK + Z Controller ===");
  Serial.println("Comandi: a1..h8 | home | cemetery | x,y | z+10 / z-10 (rel) | z0 / z20 (abs) | pos");
  Serial.printf("Asse Z: 1/%d, riduzione 1:%.0f, T8 lead %.1f mm -> %.2f step/mm | Comp. caduta a1->a8: +%.2f mm\n",
                MICROSTEPPING_Z, GEAR_RATIO_Z, LEAD_Z_MM, STEPS_PER_MM_Z, Z_DROOP_MM_A1_TO_A8);
  printStatus();
}

void loop() {
  if (Serial.available() <= 0) {
    return;
  }

  String input = Serial.readStringUntil('\n');
  input.trim();
  if (input.length() == 0) {
    return;
  }

  String lower = input;
  lower.toLowerCase();
  if (lower == "pos" || lower == "?") {
    printStatus();
    return;
  }

  // Comandi asse Z: z+10 / z-10 (relativo) oppure z0 / z20 (assoluto)
  bool isRelativeZ = false;
  double zValMm = 0.0;
  if (parseZCommand(input, isRelativeZ, zValMm)) {
    const double targetZMm = isRelativeZ ? (currentZMm + zValMm) : zValMm;
    const double compZMm = zCompensationMm(currentY);
    const long targetStepsZ = lround((targetZMm + compZMm) * STEPS_PER_MM_Z);
    const long deltaStepsZ = targetStepsZ - currentStepsZ;

    Serial.printf("Asse Z (%s %+.2f mm) -> target Z: %.2f mm (comp %+.2f mm) | Delta step Z: %ld\n",
                  isRelativeZ ? "rel" : "abs", zValMm, targetZMm, compZMm, deltaStepsZ);

    moveMotorZ(deltaStepsZ);

    currentZMm = targetZMm;
    currentStepsZ = targetStepsZ;
    Serial.println("Arrivato Z.");
    return;
  }

  double targetX = 0.0;
  double targetY = 0.0;
  String label;
  if (!parseCommandToTarget(input, targetX, targetY, label)) {
    Serial.printf("Comando non valido: '%s'. Usa a1..h8, home, cemetery, x,y oppure z+10 / z-10\n",
                  input.c_str());
    return;
  }

  double targetAngleL = 0.0;
  double targetAngleR = 0.0;
  if (label == "home") {
    // Ritorno esatto agli step (0, 0) della posizione fisica di partenza
    targetAngleL = homeAngleL;
    targetAngleR = homeAngleR;
  } else {
    String errMsg;
    if (!computeIK(targetX, targetY, targetAngleL, targetAngleR, errMsg)) {
      Serial.printf("Errore IK per %s (%.2f, %.2f): %s\n",
                    label.c_str(), targetX, targetY, errMsg.c_str());
      return;
    }
  }

  // Calcolo step assoluti rispetto agli angoli di home (0,0) per evitare accumulo di errori di arrotondamento
  const long targetStepsL = lround((targetAngleL - homeAngleL) * STEPS_PER_DEG_L);
  const long targetStepsR = lround((targetAngleR - homeAngleR) * STEPS_PER_DEG_R);
  const double targetCompZMm = zCompensationMm(targetY);
  const long targetStepsZ = lround((currentZMm + targetCompZMm) * STEPS_PER_MM_Z);

  const long deltaStepsL = targetStepsL - currentStepsL;
  const long deltaStepsR = targetStepsR - currentStepsR;
  const long deltaStepsZ = targetStepsZ - currentStepsZ;

  Serial.printf("Spostamento verso %s -> XY: (%.2f, %.2f) | Comp Z: %+.2f mm | Angoli L/R: (%.2f, %.2f) deg | Delta step L/R/Z: (%ld, %ld, %ld)\n",
                label.c_str(), targetX, targetY, targetCompZMm, targetAngleL, targetAngleR,
                deltaStepsL, deltaStepsR, deltaStepsZ);

  // Muove Z separatamente da L/R per evitare picchi di corrente/perdita passi con 3 motori insieme:
  // sale PRIMA di muovere XY (così non striscia) e scende DOPO aver mosso XY
  if (deltaStepsZ > 0) {
    moveMotorZ(deltaStepsZ);
    moveMotorsSimultaneous(deltaStepsL, deltaStepsR);
  } else {
    moveMotorsSimultaneous(deltaStepsL, deltaStepsR);
    moveMotorZ(deltaStepsZ);
  }

  currentX = targetX;
  currentY = targetY;
  currentAngleL = targetAngleL;
  currentAngleR = targetAngleR;
  currentStepsL = targetStepsL;
  currentStepsR = targetStepsR;
  currentStepsZ = targetStepsZ;

  Serial.println("Arrivato.");
}
