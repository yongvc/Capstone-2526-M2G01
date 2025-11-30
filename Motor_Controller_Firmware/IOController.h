#ifndef IOCONTROLLER_H
#define IOCONTROLLER_H

#include <Arduino.h>

class IOController {
public:
    IOController();
    void init();
    
    // Digital IOs
    bool readDigital(uint8_t index);
    void writeDigital(uint8_t index, bool state); // If they are output capable
    
    // Limit Switches
    bool readLimitSwitch(uint8_t axis_index); // 0=X, 1=Y, 2=Z

private:
    uint8_t _ioPins[5];
};

#endif
