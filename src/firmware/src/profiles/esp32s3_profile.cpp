#include "esp32s3_profile.h"

namespace {
static const PinEntry PIN_TABLE_ESP32S3[] = {
  {"MAIN", "GPIO",     "0",  "GPIO_LIMITED",    "Strapping/boot pin; use with care",                          0,  true},

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
  {"MAIN", "GPIO",     "20", "GPIO_LIMITED",    "Native USB D+ capable; board/USB-mode dependent",           20,  true},

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
  {"MAIN", "GPIO",     "37", "GPIO_LIMITED",    "Board-dependent; may overlap PSRAM/JTAG on some modules",    37,  true},
  {"MAIN", "GPIO",     "38", "GPIO_LIMITED",    "Board-dependent; may overlap PSRAM/JTAG on some modules",    38,  true},

  {"MAIN", "GPIO",     "39", "GPIO_LIMITED",    "Board-dependent; often JTAG/debug-capable",                  39,  true},
  {"MAIN", "GPIO",     "40", "GPIO_LIMITED",    "Board-dependent; often JTAG/debug-capable",                  40,  true},
  {"MAIN", "GPIO",     "41", "GPIO_LIMITED",    "Board-dependent; often JTAG/debug-capable",                  41,  true},
  {"MAIN", "GPIO",     "42", "GPIO_LIMITED",    "Board-dependent; often JTAG/debug-capable",                  42,  true},

  {"MAIN", "GPIO",     "43", "UART_CONSOLE",    "Often UART0 TX on dev boards",                              43,  false},
  {"MAIN", "GPIO",     "44", "UART_CONSOLE",    "Often UART0 RX on dev boards",                              44,  false},

  {"MAIN", "GPIO",     "45", "BOOT_STRAP",      "Strapping/boot pin",                                        -1,  false},
  {"MAIN", "GPIO",     "46", "BOOT_STRAP",      "Strapping/boot pin",                                        -1,  false},

  {"MAIN", "GPIO",     "47", "GPIO_FREE",       "General-purpose GPIO",                                      47,  true},
  {"MAIN", "GPIO",     "48", "GPIO_FREE",       "General-purpose GPIO",                                      48,  true},
};

static const PinCatalogProfile kProfileEsp32S3 = {
  "esp32s3-default",
  "esp32s3",
  PIN_TABLE_ESP32S3,
  sizeof(PIN_TABLE_ESP32S3) / sizeof(PIN_TABLE_ESP32S3[0]),
};
}  // namespace

const PinCatalogProfile& esp32s3Profile() {
  return kProfileEsp32S3;
}
