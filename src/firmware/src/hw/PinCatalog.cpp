// PinCatalog: static pin metadata table for ESP32-S3.

#include "hw/PinCatalog.h"

static const PinEntry PIN_TABLE[] = {
  {"MAIN", "RESERVED", "0",  "BOOT_STRAP",      "Strapping/boot pin",                                        -1,  false},

  {"MAIN", "GPIO",     "1",  "GPIO_FREE",       "General-purpose GPIO",                                       1,  true},
  {"MAIN", "GPIO",     "2",  "GPIO_FREE",       "General-purpose GPIO",                                       2,  true},
  {"MAIN", "GPIO",     "3",  "BOOT_STRAP",      "Strapping/boot pin; affects boot mode selection",           3,  false},

  {"MAIN", "GPIO",     "4",  "GPIO_FREE",       "General-purpose GPIO",                                       4,  true},
  {"MAIN", "GPIO",     "5",  "GPIO_FREE",       "General-purpose GPIO",                                       5,  true},
  {"MAIN", "GPIO",     "6",  "GPIO_FREE",       "General-purpose GPIO",                                       6,  true},
  {"MAIN", "GPIO",     "7",  "GPIO_FREE",       "General-purpose GPIO",                                       7,  true},
  {"MAIN", "GPIO",     "8",  "GPIO_FREE",       "General-purpose GPIO",                                       8,  true},
  {"MAIN", "GPIO",     "9",  "GPIO_FREE",       "General-purpose GPIO",                                       9,  true},
  {"MAIN", "GPIO",     "10", "GPIO_FREE",       "General-purpose GPIO",                                      10,  true},
  {"MAIN", "GPIO",     "11", "GPIO_FREE",       "General-purpose GPIO",                                      11,  true},
  {"MAIN", "GPIO",     "12", "GPIO_FREE",       "General-purpose GPIO",                                      12,  true},
  {"MAIN", "GPIO",     "13", "GPIO_FREE",       "General-purpose GPIO",                                      13,  true},
  {"MAIN", "GPIO",     "14", "GPIO_FREE",       "General-purpose GPIO",                                      14,  true},
  {"MAIN", "GPIO",     "15", "GPIO_FREE",       "General-purpose GPIO",                                      15,  true},
  {"MAIN", "GPIO",     "16", "GPIO_FREE",       "General-purpose GPIO",                                      16,  true},
  {"MAIN", "GPIO",     "17", "GPIO_FREE",       "General-purpose GPIO",                                      17,  true},

  {"MAIN", "GPIO",     "18", "GPIO_LIMITED",    "May be board-dependent",                                    18,  true},

  {"MAIN", "USB_D-",   "19", "USB_NATIVE",      "Native USB D- (USB-OTG)",                                   -1,  false},
  {"MAIN", "USB_D+",   "20", "USB_NATIVE",      "Native USB D+ (USB-OTG)",                                   -1,  false},

  {"MAIN", "GPIO",     "21", "GPIO_FREE",       "General-purpose GPIO",                                      21,  true},

  {"MAIN", "FLASH_IO", "26", "FLASH_BUS",       "Used by SPI flash/PSRAM bus",                               -1,  false},
  {"MAIN", "FLASH_IO", "27", "FLASH_BUS",       "Used by SPI flash/PSRAM bus",                               -1,  false},
  {"MAIN", "FLASH_IO", "28", "FLASH_BUS",       "Used by SPI flash/PSRAM bus",                               -1,  false},
  {"MAIN", "FLASH_IO", "29", "FLASH_BUS",       "Used by SPI flash/PSRAM bus",                               -1,  false},
  {"MAIN", "FLASH_CLK","30", "FLASH_BUS",       "Used by SPI flash/PSRAM bus",                               -1,  false},
  {"MAIN", "FLASH_CS", "31", "FLASH_BUS",       "Used by SPI flash/PSRAM bus",                               -1,  false},
  {"MAIN", "FLASH_HD", "32", "FLASH_BUS",       "Used by SPI flash/PSRAM bus",                               -1,  false},

  {"MAIN", "GPIO",     "33", "PSRAM_BUS",       "May be connected to Octal flash/PSRAM on some modules",      33,  false},
  {"MAIN", "GPIO",     "34", "PSRAM_BUS",       "May be connected to Octal flash/PSRAM on some modules",      34,  false},
  {"MAIN", "GPIO",     "35", "PSRAM_BUS",       "May be connected to Octal flash/PSRAM on some modules",      35,  false},
  {"MAIN", "GPIO",     "36", "PSRAM_BUS",       "May be connected to Octal flash/PSRAM on some modules",      36,  false},
  {"MAIN", "GPIO",     "37", "PSRAM_BUS",       "May be connected to Octal flash/PSRAM on some modules",      37,  false},
  {"MAIN", "GPIO",     "38", "PSRAM_BUS",       "May be connected to Octal flash/PSRAM on some modules",      38,  false},

  {"MAIN", "JTAG",     "39", "JTAG_DEBUG",      "JTAG/debug pin",                                            -1,  false},
  {"MAIN", "JTAG",     "40", "JTAG_DEBUG",      "JTAG/debug pin",                                            -1,  false},
  {"MAIN", "JTAG",     "41", "JTAG_DEBUG",      "JTAG/debug pin",                                            -1,  false},
  {"MAIN", "JTAG",     "42", "JTAG_DEBUG",      "JTAG/debug pin",                                            -1,  false},

  {"MAIN", "GPIO",     "43", "UART_CONSOLE",    "Often UART0 TX on dev boards",                              43,  false},
  {"MAIN", "GPIO",     "44", "UART_CONSOLE",    "Often UART0 RX on dev boards",                              44,  false},

  {"MAIN", "GPIO",     "45", "BOOT_STRAP",      "Strapping/boot pin",                                        -1,  false},
  {"MAIN", "GPIO",     "46", "BOOT_STRAP",      "Strapping/boot pin",                                        -1,  false},

  {"MAIN", "GPIO",     "47", "GPIO_FREE",       "General-purpose GPIO",                                      47,  true},
  {"MAIN", "GPIO",     "48", "GPIO_FREE",       "General-purpose GPIO",                                      48,  true},
};

size_t PinCatalog::count() {
  return sizeof(PIN_TABLE) / sizeof(PIN_TABLE[0]);
}

const PinEntry& PinCatalog::at(size_t index) {
  return PIN_TABLE[index];
}
