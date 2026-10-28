// 카드 정렬 확인 프로그램 - 보드 쪽 코드 (아두이노 우노, ESP32 모두 이 파일 하나로 쓴다)
// 파이썬(board.py)에서 시리얼로 보내는 명령을 받아 RGB LED와 I2C LCD를 제어한다.
//   L,r,g,b          RGB LED 색 (0~255)
//   C                LCD 지우기
//   P,col,row,text   LCD (col, row) 위치에 글자 쓰기
//   ?                준비 신호 다시 보내기
// 켜지면 바로 "BOOT sort_board" 를 보내고, LCD를 찾은 뒤 "READY sort_board LCD=0x27" 처럼
// 준비 신호를 보낸다. (LCD를 못 찾으면 LCD=none)
//
// 필요한 라이브러리: LiquidCrystal I2C (Frank de Brabander)
//
// 배선
//              우노        ESP32 (DevKit, WROOM-32)
//   LED R      9           25
//   LED G      10          26
//   LED B      11          27
//   LCD SDA    A4          21
//   LCD SCL    A5          22
// ESP32 의 6~11번 핀은 내부 플래시용이라 쓰면 안 된다.

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

#if defined(ESP32)
const int PIN_R = 25;
const int PIN_G = 26;
const int PIN_B = 27;
#else
const int PIN_R = 9;
const int PIN_G = 10;
const int PIN_B = 11;
#endif

// ESP32 보드 패키지 2.x 에는 analogWrite 가 없어서 LEDC 로 밝기를 조절한다
#if defined(ESP32) && defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR < 3
#define USE_LEDC 1
#endif

// LCD 주소는 I2C 버스를 훑어서 처음 찾은 장치로 정한다 (보통 0x27, 0x3F, 0x20)
LiquidCrystal_I2C *lcd = NULL;
byte lcdAddress = 0;

String line;

byte findI2CDevice() {
  for (byte addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) return addr;
  }
  return 0;
}

void sendReady() {
  Serial.print("READY sort_board LCD=");
  if (lcdAddress) {
    Serial.print("0x");
    Serial.println(lcdAddress, HEX);
  } else {
    Serial.println("none");
  }
}

void setupRGB() {
#if defined(USE_LEDC)
  const int pins[] = {PIN_R, PIN_G, PIN_B};
  for (int ch = 0; ch < 3; ch++) {
    ledcSetup(ch, 5000, 8);
    ledcAttachPin(pins[ch], ch);
  }
#else
  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
#endif
}

void setRGB(int r, int g, int b) {
#if defined(USE_LEDC)
  ledcWrite(0, constrain(r, 0, 255));
  ledcWrite(1, constrain(g, 0, 255));
  ledcWrite(2, constrain(b, 0, 255));
#else
  analogWrite(PIN_R, constrain(r, 0, 255));
  analogWrite(PIN_G, constrain(g, 0, 255));
  analogWrite(PIN_B, constrain(b, 0, 255));
#endif
}

void handle(const String &cmd) {
  if (cmd.length() == 0) return;

  if (cmd.charAt(0) == '?') {
    sendReady();
  } else if (cmd.charAt(0) == 'L') {
    int a = cmd.indexOf(',', 2);
    int b = cmd.indexOf(',', a + 1);
    setRGB(cmd.substring(2, a).toInt(),
           cmd.substring(a + 1, b).toInt(),
           cmd.substring(b + 1).toInt());
  } else if (lcd == NULL) {
    return;
  } else if (cmd.charAt(0) == 'C') {
    lcd->clear();
  } else if (cmd.charAt(0) == 'P') {
    int a = cmd.indexOf(',', 2);
    int b = cmd.indexOf(',', a + 1);
    lcd->setCursor(cmd.substring(2, a).toInt(), cmd.substring(a + 1, b).toInt());
    lcd->print(cmd.substring(b + 1));
  }
}

void setup() {
  Serial.begin(115200);
  Serial.println("BOOT sort_board");
  setupRGB();
  setRGB(0, 0, 0);

  Wire.begin();
#if defined(WIRE_HAS_TIMEOUT)
  // LCD 배선이 불안정해도 I2C 통신에서 멈추지 않도록 시간 제한을 둔다
  Wire.setWireTimeout(3000, true);
#endif
  lcdAddress = findI2CDevice();
  if (lcdAddress) {
    lcd = new LiquidCrystal_I2C(lcdAddress, 16, 2);
    lcd->init();
    lcd->backlight();
    lcd->clear();
    lcd->print("Ready");
  }
  sendReady();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      handle(line);
      line = "";
    } else if (c != '\r') {
      line += c;
    }
  }
}
