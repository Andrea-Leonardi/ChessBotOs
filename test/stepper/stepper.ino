// Test controllo 3 motori stepper NEMA 17 (17HS19) con driver A4988 su ESP32
// Cablaggio e microstepping:
//   mot_L -> DIR: G19, STEP: G18 (1/16: MS1, MS2, MS3 = HIGH)
//   mot_R -> DIR: G25, STEP: G32 (1/16: MS1, MS2, MS3 = HIGH)
//   mot_Z -> DIR: G17, STEP: G5  (1/4:  MS2 = HIGH, MS1/MS3 = LOW)

#include <Arduino.h>

struct StepperMotor {
  const char* name;
  int dirPin;
  int stepPin;
  int microstepping;
  int turns;
  long minFreqHz;
  long maxFreqHz;
  long rampSteps;
};

constexpr StepperMotor mot_L = {"mot_L", 19, 18, 16, 1, 1500, 4000, 800};
constexpr StepperMotor mot_R = {"mot_R", 25, 32, 16, 1, 1500, 4000, 800};
constexpr StepperMotor mot_Z = {"mot_Z", 17,  5,  4, 5,  500, 4500, 600};

constexpr StepperMotor MOTORS[] = {mot_L, mot_R, mot_Z};

// Parametri motore e temporizzazione impulsi STEP
constexpr int FULL_STEPS_PER_REV       = 200; // 17HS19: 1.8 gradi/step -> 200 step/giro
constexpr long STEP_PULSE_US           = 2;   // A4988 richiede almeno 1 us HIGH
constexpr unsigned long PAUSE_BETWEEN_MS = 400; // Pausa tra cambi di direzione/motore

long stepsPerRev(const StepperMotor& motor) {
  return static_cast<long>(FULL_STEPS_PER_REV) * motor.microstepping;
}

void initMotor(const StepperMotor& motor) {
  pinMode(motor.dirPin, OUTPUT);
  pinMode(motor.stepPin, OUTPUT);
  digitalWrite(motor.dirPin, LOW);
  digitalWrite(motor.stepPin, LOW);
}

void rotateSteps(const StepperMotor& motor, long steps, bool clockwise) {
  digitalWrite(motor.dirPin, clockwise ? HIGH : LOW);
  delayMicroseconds(10); // Tempo di setup del segnale DIR prima del fronte STEP

  const long ramp = min(motor.rampSteps, steps / 2);
  const long startFreq = min(motor.minFreqHz, motor.maxFreqHz);
  const long freqSpan = motor.maxFreqHz - startFreq;

  for (long i = 0; i < steps; i++) {
    long freqHz = motor.maxFreqHz;

    if (ramp > 0 && freqSpan > 0) {
      if (i < ramp) {
        // Accelerazione con rampa lineare in frequenza
        freqHz = startFreq + (freqSpan * i) / ramp;
      } else if (i >= steps - ramp) {
        // Decelerazione
        const long remaining = steps - 1 - i;
        freqHz = startFreq + (freqSpan * remaining) / ramp;
      }
    }

    const long stepPeriodUs = 1000000L / freqHz;

    digitalWrite(motor.stepPin, HIGH);
    delayMicroseconds(STEP_PULSE_US);
    digitalWrite(motor.stepPin, LOW);

    const long lowDelayUs = stepPeriodUs - STEP_PULSE_US;
    if (lowDelayUs > 0) {
      delayMicroseconds(lowDelayUs);
    }
  }
}

void testMotorCycle(const StepperMotor& motor) {
  const long targetSteps = stepsPerRev(motor) * motor.turns;

  Serial.printf("[%s] %d giri avanti (%ld step @ %ld Hz, 1/%d, DIR = HIGH)\n",
                motor.name, motor.turns, targetSteps, motor.maxFreqHz, motor.microstepping);
  rotateSteps(motor, targetSteps, true);
  delay(PAUSE_BETWEEN_MS);

  Serial.printf("[%s] %d giri indietro (%ld step @ %ld Hz, 1/%d, DIR = LOW)\n",
                motor.name, motor.turns, targetSteps, motor.maxFreqHz, motor.microstepping);
  rotateSteps(motor, targetSteps, false);
  delay(PAUSE_BETWEEN_MS);
}

void setup() {
  Serial.begin(115200);
  for (const auto& motor : MOTORS) {
    initMotor(motor);
  }

  delay(500);
  Serial.println("Avvio test sequenziale 3 stepper (mot_L -> mot_R -> mot_Z)");
  for (const auto& motor : MOTORS) {
    Serial.printf("  %s: 1/%d (%ld step/giro) -> %d giri (%ld step) @ %ld Hz\n",
                  motor.name, motor.microstepping, stepsPerRev(motor),
                  motor.turns, stepsPerRev(motor) * motor.turns, motor.maxFreqHz);
  }
}

void loop() {
  for (const auto& motor : MOTORS) {
    testMotorCycle(motor);
  }
}
