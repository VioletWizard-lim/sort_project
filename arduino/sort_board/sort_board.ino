// 버블 정렬 카드 게임 - 아두이노 우노 쪽 코드
// 파이썬(board.py)에서 시리얼로 보내는 명령을 받아 RGB LED와 I2C LCD를 제어한다.
//   L,r,g,b          RGB LED 색 (0~255)
//   C                LCD 지우기
//   P,col,row,text   LCD (col, row) 위치에 글자 쓰기
//
// 필요한 라이브러리: LiquidCrystal I2C (Frank de Brabander)

#include <Wire.h>
#include <LiquidCrystal_I2C.h>

const int PIN_R = 9;
const int PIN_G = 10;
const int PIN_B = 11;

// Scratch 프로젝트와 같은 주소. LCD가 안 나오면 0x27 또는 0x3F로 바꿔 보세요.
LiquidCrystal_I2C lcd(0x20, 16, 2);

String line;

void setRGB(int r, int g, int b) {
  analogWrite(PIN_R, constrain(r, 0, 255));
  analogWrite(PIN_G, constrain(g, 0, 255));
  analogWrite(PIN_B, constrain(b, 0, 255));
}

void handle(const String &cmd) {
  if (cmd.length() == 0) return;

  if (cmd.charAt(0) == 'C') {
    lcd.clear();
  } else if (cmd.charAt(0) == 'L') {
    int a = cmd.indexOf(',', 2);
    int b = cmd.indexOf(',', a + 1);
    setRGB(cmd.substring(2, a).toInt(),
           cmd.substring(a + 1, b).toInt(),
           cmd.substring(b + 1).toInt());
  } else if (cmd.charAt(0) == 'P') {
    int a = cmd.indexOf(',', 2);
    int b = cmd.indexOf(',', a + 1);
    lcd.setCursor(cmd.substring(2, a).toInt(), cmd.substring(a + 1, b).toInt());
    lcd.print(cmd.substring(b + 1));
  }
}

void setup() {
  Serial.begin(9600);
  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
  setRGB(0, 0, 0);
  lcd.init();
  lcd.backlight();
  lcd.clear();
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
