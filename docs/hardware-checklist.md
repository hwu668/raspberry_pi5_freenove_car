# Hardware Checklist

在实车测试前，逐项检查以下内容。

## Power

- [ ] 电池已充电
- [ ] 电源开关已打开
- [ ] 电机供电正常
- [ ] Raspberry Pi 供电稳定

## Raspberry Pi interfaces

- [ ] I2C enabled (`sudo raspi-config` → Interface Options → I2C → Enable)
- [ ] SPI enabled (`sudo raspi-config` → Interface Options → SPI → Enable)
- [ ] Camera interface enabled / camera detected (`libcamera-hello --list-cameras`)
- [ ] SSH enabled if running headless

## Camera

- [ ] Camera cable connected correctly (蓝色标签朝向网口方向)
- [ ] Camera can capture test image (`libcamera-still -o test.jpg`)
- [ ] Preview works locally or through remote display
- [ ] Headless mode works with `--no-display`

## Motor

- [ ] Front-left motor responds
- [ ] Front-right motor responds
- [ ] Rear-left motor responds
- [ ] Rear-right motor responds
- [ ] Forward direction is correct (all wheels forward)
- [ ] Backward direction is correct (all wheels backward)
- [ ] Left / right turn direction is correct (left wheels backward, right wheels forward = left turn)

## Ultrasonic sensor

- [ ] TRIG connected correctly (BCM 23)
- [ ] ECHO connected correctly (BCM 24)
- [ ] Distance reading is stable (press `i` in program to read)
- [ ] STOP threshold is reasonable (default 10 cm)

## Servo / LED / Buzzer

- [ ] Servo responds (press `1/2/3` to test pan angles)
- [ ] LED responds (changes color with navigation state)
- [ ] Buzzer responds (beeps on stop / test with `m` key)
