#include <Servo.h>

Servo myservo;

const int servoPin = 3;
const int minPulse = 500;
const int maxPulse = 2500;

void setup() {
  Serial.begin(9600);

  myservo.attach(servoPin, minPulse, maxPulse);
  myservo.writeMicroseconds(1500); // Initial position: 135 deg

  Serial.println("Enter an angle between 0 and 270:");
}

void loop() {
  if (Serial.available() > 0) {

    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input.length() == 0) return;

    for (int i = 0; i < input.length(); i++) {
      if (!isDigit(input[i])) {
        Serial.println("Please enter a valid number.");
        return;
      }
    }

    int angle = input.toInt();

    if (angle >= 0 && angle <= 270) {

      int pulse = map(angle, 0, 270, minPulse, maxPulse);
      myservo.writeMicroseconds(pulse);

      Serial.print("Servo moved to: ");
      Serial.print(angle);
      Serial.println(" degrees");

    } else {
      Serial.println("Error: enter an angle between 0 and 270.");
    }
  }
}
