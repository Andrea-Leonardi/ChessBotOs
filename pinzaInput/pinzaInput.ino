#include <Servo.h>

Servo myservo;

const int servoPin = 3;
const int minPulse = 500;
const int maxPulse = 2500;

void setup() {
  Serial.begin(9600);

  myservo.attach(servoPin, minPulse, maxPulse);
  myservo.writeMicroseconds(1500); // Posizione iniziale: 135°

  Serial.println("Inserisci un angolo tra 0 e 270:");
}

void loop() {
  if (Serial.available() > 0) {

    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() == 0) return;

    for (int i = 0; i < input.length(); i++) {
      if (!isDigit(input[i])) {
        Serial.println("Inserisci un numero valido.");
        return;
      }
    }

    int angolo = input.toInt();

    if (angolo >= 0 && angolo <= 270) {

      int pulse = map(angolo, 0, 270, minPulse, maxPulse);
      myservo.writeMicroseconds(pulse);

      Serial.print("Servo posizionato a: ");
      Serial.print(angolo);
      Serial.println(" gradi");

    } else {
      Serial.println("Errore: inserisci un angolo tra 0 e 270.");
    }
  }
}