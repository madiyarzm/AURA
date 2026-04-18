#define FASTLED_ALLOW_INTERRUPTS 1
#include <FastLED.h>
#include <Servo.h>

#define NUM_LEDS 50
#define DATA_PIN 12
#define BRIGHTNESS 100

#define SERVO_H_PIN 9
#define SERVO_V_PIN 8
#define SERVO_H_CENTER 80
#define SERVO_V_CENTER 60

CRGB leds[NUM_LEDS];
Servo servoH;
Servo servoV;

// ----------- EXPRESIONES -----------
void beSad() {
  FastLED.clear();
  leds[0] = CRGB::Blue; leds[1] = CRGB::Blue;
  leds[3] = CRGB::Blue; leds[4] = CRGB::Blue;
  leds[8] = CRGB::Blue; leds[9] = CRGB::Blue;
  leds[24] = CRGB::Blue; leds[25] = CRGB::Blue;
  leds[49] = CRGB::Blue;
  leds[11] = CRGB::Blue; leds[12] = CRGB::Blue; leds[13] = CRGB::Blue;
  leds[17] = CRGB::Blue; leds[20] = CRGB::Blue;
  leds[37] = CRGB::Blue; leds[36] = CRGB::Blue;
  leds[42] = CRGB::Blue; leds[43] = CRGB::Blue; leds[44] = CRGB::Blue;
}

void beAngry() {
  FastLED.clear();
  leds[0] = CRGB::Red; leds[1] = CRGB::Red;
  leds[3] = CRGB::Red; leds[9] = CRGB::Red;
  leds[24] = CRGB::Red; leds[25] = CRGB::Red;
  leds[28] = CRGB::Red; leds[33] = CRGB::Red;
  leds[49] = CRGB::Red;
  leds[11] = CRGB::Red; leds[12] = CRGB::Red; leds[13] = CRGB::Red;
  leds[17] = CRGB::Red; leds[20] = CRGB::Red;
  leds[37] = CRGB::Red; leds[36] = CRGB::Red;
  leds[42] = CRGB::Red; leds[43] = CRGB::Red; leds[44] = CRGB::Red;
}

void neutralOpenEyes() {
  FastLED.clear();
  leds[0] = CRGB::Blue; leds[1] = CRGB::Blue;
  leds[24] = CRGB::Blue; leds[25] = CRGB::Blue;
  leds[49] = CRGB::Blue;
  leds[11] = CRGB::Blue; leds[12] = CRGB::Blue; leds[13] = CRGB::Blue;
  leds[37] = CRGB::Blue; leds[36] = CRGB::Blue;
  leds[42] = CRGB::Blue; leds[43] = CRGB::Blue; leds[44] = CRGB::Blue;
}

void neutralCloseEyes() {
  FastLED.clear();
  leds[0] = CRGB::Blue; leds[25] = CRGB::Blue;
  leds[12] = CRGB::Blue; leds[36] = CRGB::Blue;
  leds[42] = CRGB::Blue; leds[43] = CRGB::Blue; leds[44] = CRGB::Blue;
}

// ----------- SERVOS -----------
void setServoH(int angle) {
  angle = constrain(angle, 0, 180);
  servoH.attach(SERVO_H_PIN);
  servoH.write(angle);
  delay(400);
  servoH.detach();
}

void setServoV(int angle) {
  angle = constrain(angle, 0, 180);
  servoV.attach(SERVO_V_PIN);
  servoV.write(angle);
  delay(400);
  servoV.detach();
}

// ----------- SWEEP -----------
void sweepServo(Servo &srv, int centerAngle, int minAngle, int maxAngle, int stepDelay) {
  for (int a = centerAngle; a <= maxAngle; a++) { srv.write(a); delay(stepDelay); }
  for (int a = maxAngle; a >= minAngle; a--)    { srv.write(a); delay(stepDelay); }
  for (int a = minAngle; a <= centerAngle; a++) { srv.write(a); delay(stepDelay); }
}

void doSweepH(int stepDelay) {
  int lo = max(0,   SERVO_H_CENTER - 40);
  int hi = min(180, SERVO_H_CENTER + 40);
  Serial.print("sweep H "); Serial.print(lo); Serial.print("->"); Serial.println(hi);
  sweepServo(servoH, SERVO_H_CENTER, lo, hi, stepDelay);
  Serial.println("ok");
}

void doSweepV(int stepDelay) {
  int lo = max(0,   SERVO_V_CENTER - 30);
  int hi = min(180, SERVO_V_CENTER + 30);
  Serial.print("sweep V "); Serial.print(lo); Serial.print("->"); Serial.println(hi);
  sweepServo(servoV, SERVO_V_CENTER, lo, hi, stepDelay);
  Serial.println("ok");
}

void doNod() {
  Serial.println("nod");
  for (int i = 0; i < 3; i++) {
    servoV.write(constrain(SERVO_V_CENTER + 20, 0, 180)); delay(200);
    servoV.write(constrain(SERVO_V_CENTER - 20, 0, 180)); delay(200);
  }
  servoV.write(SERVO_V_CENTER);
  Serial.println("ok");
}

void doShake() {
  Serial.println("shake");
  for (int i = 0; i < 3; i++) {
    servoH.write(constrain(SERVO_H_CENTER + 25, 0, 180)); delay(150);
    servoH.write(constrain(SERVO_H_CENTER - 25, 0, 180)); delay(150);
  }
  servoH.write(SERVO_H_CENTER);
  Serial.println("ok");
}

// ----------- PARSER -----------
void parseCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  if (cmd.startsWith("expr:")) {
    String expr = cmd.substring(5);
    if      (expr == "sad")           beSad();
    else if (expr == "angry")         beAngry();
    else if (expr == "neutral_open")  neutralOpenEyes();
    else if (expr == "neutral_close") neutralCloseEyes();
    else if (expr == "test") {
      FastLED.clear();
      leds[0] = CRGB(255,0,0); leds[1] = CRGB(0,255,0);
      leds[2] = CRGB(0,255,0); leds[3] = CRGB(0,0,255);
      leds[4] = CRGB(0,0,255); leds[5] = CRGB(0,0,255);
    }
    FastLED.show();
  }
  else if (cmd.startsWith("servo:")) {
    String sub = cmd.substring(6);
    if (sub == "center") {
      setServoH(SERVO_H_CENTER); setServoV(SERVO_V_CENTER);
      Serial.println("ok — centered");
    }
    else if (sub.startsWith("h:")) {
      int angle = sub.substring(2).toInt();
      setServoH(angle);
      Serial.print("ok — H = "); Serial.println(angle);
    }
    else if (sub.startsWith("v:")) {
      int angle = sub.substring(2).toInt();
      setServoV(angle);
      Serial.print("ok — V = "); Serial.println(angle);
    }
  }
  else if (cmd.startsWith("sweep:")) {
    String sub = cmd.substring(6);
    if      (sub == "h")       doSweepH(15);
    else if (sub == "h:fast")  doSweepH(6);
    else if (sub == "v")       doSweepV(15);
    else if (sub == "v:fast")  doSweepV(6);
    else if (sub == "all")   { doSweepH(15); doSweepV(15); }
    else if (sub == "nod")     doNod();
    else if (sub == "shake")   doShake();
    else Serial.println("err — unknown sweep");
  }
  else {
    Serial.println("err — unknown command");
  }
}

// ----------- DEBUG LED -----------
void blink() {
  digitalWrite(2, HIGH); delay(100); digitalWrite(2, LOW);
}

// ----------- SETUP -----------
void setup() {
  Serial.begin(9600);
  pinMode(2, OUTPUT);

  FastLED.addLeds<WS2811, DATA_PIN>(leds, NUM_LEDS);
  FastLED.setBrightness(BRIGHTNESS);
  FastLED.clear();
  FastLED.show();

  setServoH(SERVO_H_CENTER);
  setServoV(SERVO_V_CENTER);

  Serial.println("READY");
  Serial.println("  expr:sad / angry / neutral_open / neutral_close / test");
  Serial.println("  servo:h:<0-180>  servo:v:<0-180>  servo:center");
  Serial.println("  sweep:h  sweep:v  sweep:h:fast  sweep:v:fast");
  Serial.println("  sweep:all  sweep:nod  sweep:shake");
}

// ----------- LOOP -----------
String inputBuffer = "";

void loop() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == '\n') {
      blink();
      parseCommand(inputBuffer);
      inputBuffer = "";
    } else if (c != '\r') {
      inputBuffer += c;
    }
  }
}
