#ifndef CONFIG_H
#define CONFIG_H

// Serial Communication
#define SERIAL_BAUD_RATE 115200

// Stepper Configuration (TMC2209)
#define R_SENSE 0.11f // Sense resistor value in Ohms (standard for silentstepstick)
#define DRIVER_ADDRESS 0b00 // TMC2209 UART address (usually 0 if single driver per UART line, or addressed)

// Servo Configuration
#define SERVO_MIN_US 500
#define SERVO_MAX_US 2400

// LED Configuration
#define LED_BLINK_INTERVAL_MS 500

#endif // CONFIG_H
