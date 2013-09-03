#!/usr/bin/python

# python bootloader programming util
# this is a simple python MCU programming util that works with pybootloader
# originally made for pyMCU with firmware 1.0.8 or higher
# this can be used to flash other custom firmware programs as well
# just be sure to offset your programs start address to 0x1C0
#
# (C) 2011-2013 Richard Wardlow
# this is distributed under a free software license, see license.txt
# http://www.circuitsforfun.com


VERSION = '1.0.1'

import sys, os, serial, time
from optparse import OptionParser


def addCommandLineOptions(parser):
    parser.add_option(
            '-f', '--file',
            dest='hexFile',
            default=None,
            help='Specify Hex file to program on MCU')
    parser.add_option(
            '-i', '--ignore',
            dest='ignoreStart',
            default='0',
            help='Ignore first two bytes at 0 for linkers that don\'t properly offset for bootloaders')
    parser.add_option(
            '-p', '--port',
            dest='commPort',
            default=None,
            help='Manually set the comm port to use for communications\nDefault is set to Auto find Comm Port.')
    parser.add_option(
            '-v', '--verify',
            dest='readVerify',
            default='1',
            help='Verify Programmed Code on MCU, Set to 1 for Verify, Set to 0 to Skip, Default is 1')


def mcuScan(baudrate=115200):
    """scan for available MCUs in Bootloader mode. return a dictionary (portname, index)"""
    available = {}
    if os.name == 'nt':
        for i in range(256):
            try:
                s = serial.Serial(i,baudrate,timeout=1)
                s.write('!' + chr(0) + chr(0)+ chr(0) + chr(0))
                time.sleep(2)
                s.write('v' + chr(0) + chr(0) + chr(0) + chr(0))
                checkID = s.read(6)
                if 'pyboot' in checkID:
                    available[s.portstr] = i
                s.close()   # explicit close 'cause of delayed GC in java
            except serial.SerialException:
                pass
        return available
    if os.name == 'posix':
        for i in os.listdir('/dev/'):
            if 'ttyUSB' in i or 'usbserial' in i:
                try:
                    s = serial.Serial('/dev/' + i,baudrate,timeout=1)
                    s.write('!' + chr(0) + chr(0)+ chr(0) + chr(0))
                    time.sleep(2)
                    s.write('v' + chr(0) + chr(0) + chr(0) + chr(0))
                    checkID = s.read(6)
                    if 'pyboot' in checkID:
                        available[s.portstr] = i
                    s.close()   # explicit close 'cause of delayed GC in java
                except serial.SerialException:
                    pass
        return available

def eraseSpace(s):
    for x in range(448,16352,32):
        codeAddr = x
        bL = codeAddr & 255
        bH = codeAddr >> 8
        s.write('e' + chr(0) + chr(0) + chr(bL) + chr(bH))
        sd = ""
        while sd != "$":
            sd = s.read(1)

def verifyProgram(s, allHex):
    progLen = len(allHex)
    progCnt = 0
    errCnt = 0
    extAddr = 0
    for h in allHex:
        hs = h.strip(' \n\r')
        if hs[:1] == ':':
            hss = hs[1:]
            tb = hss[:2]
            numBytes = int('0x' + tb, 0)
            ta = hss[2:6]
            codeAddr = int('0x' + ta,0) / 2
            tc = hss[6:8]
            if tc == '04':
                ea = hss[8:12]
                extAddr = int('0x' + ea,0)
            else:
                dt = hss[8:8+numBytes*2]
                data = []
                tmp = ''
                for t in dt:
                    tmp += t
                    if len(tmp) == 2:
                        data.append(int('0x' + tmp,0))
                        tmp = ''
            if tc == '00':
                # Data Record
                fa = (extAddr << 15) + codeAddr
                if fa > 0x3FFF: # Config Bits
                    print 'Ignoring Config Bits'
                elif fa < 0x1C0: # If lower ignore, would have been caught in the write process anyway
                    pass
                else:
                    r = 0
                    for x in range(0,len(data)/2):
                        dout1 = data[r]
                        dout2 = data[r+1]
                        bL = codeAddr & 255
                        bH = codeAddr >> 8
                        s.write('r' + chr(0) + chr(0) + chr(bL) + chr(bH))
                        check = (dout2 << 8) + dout1
                        vr = s.read(4)
                        vc = int('0x' + vr,0)
                        sd = ""
                        while sd != "$":
                            sd = s.read(1)
                        r += 2
                        codeAddr += 1
                        if vc != check:
                            errCnt = errCnt + 1
            if tc == '01':
                pass # Termination Record
            if tc == '04':
                pass # Extended Address Record
        progCnt += 1
        print "Verify: (" + str(progCnt) + " of " + str(progLen) + ") Data Rows"
    return errCnt

def writeProgram(s, allHex, si='0'):
    progLen = len(allHex)
    progCnt = 0
    extAddr = 0
    for h in allHex:
        hs = h.strip(' \n\r')
        if hs[:1] == ':':
            hss = hs[1:]
            tb = hss[:2]
            numBytes = int('0x' + tb, 0)
            ta = hss[2:6]
            codeAddr = int('0x' + ta,0) / 2
            tc = hss[6:8]
            if tc == '04':
                ea = hss[8:12]
                extAddr = int('0x' + ea,0)
            else:
                dt = hss[8:8+numBytes*2]
                data = []
                tmp = ''
                for t in dt:
                    tmp += t
                    if len(tmp) == 2:
                        data.append(int('0x' + tmp,0))
                        tmp = ''
            if tc == '00':
                # Data Record
                fa = (extAddr << 15) + codeAddr
                if fa > 0x3FFF: # Config Bits
                    print 'Ignoring Config Bits'
                elif fa < 0x1C0: # If lower this will overwrite bootloader
                    if si == '0':
                        print 'Incompatible Hex file or start address was not properly set in code before compiling.'
                        sys.exit(0)
                else:
                    r = 0
                    if len(data) < 16:
                        while len(data) < 16:
                            data.append(255)
                            data.append(63)
                    for x in range(0,len(data)/2):
                        dout1 = data[r]
                        dout2 = data[r+1]
                        bL = codeAddr & 255
                        bH = codeAddr >> 8
                        s.write('w' + chr(dout1) + chr(dout2) + chr(bL) + chr(bH))
                        sd = ""
                        while sd != "$":
                            sd = s.read(1)
                        r += 2
                        codeAddr += 1
            if tc == '01':
                pass # Termination Record
            if tc == '04':
                pass # Extended Address Record
        progCnt += 1
        print "Program: (" + str(progCnt) + " of " + str(progLen) + ") Data Rows"


def pyBootProgram(options):
    s = None
    print """
    *****************************************************
    *    pyBootProgrammer - Python MCU Programmer       *
    *       Originally developed for pyMCU              *
    *       Version: """ + VERSION + """                              *
    *****************************************************\n
    """
    if options.hexFile == None:
        print 'Need to specify a hex file for programming'
        sys.exit(0)

    if options.commPort == None:
        print 'No Comm Port Specified... Attempting to find MCU in Bootloader mode automatically.'
        findmcu = mcuScan()
        if len(findmcu) > 0:
            s = serial.Serial(findmcu.items()[0][0],115200, timeout=2)
    else:
        try:
            s = serial.Serial(options.commPort,115200, timeout=2)
            s.write('!' + chr(0) + chr(0)+ chr(0) + chr(0))
            time.sleep(2)
            s.write('v' + chr(0) + chr(0) + chr(0) + chr(0))
            checkID = s.read(6)
            if 'pyboot' not in checkID:
                print "Not in Bootloader Mode, or not able to communication with bootloader on port: " + options.commPort
                sys.exit(0)
        except:
            print "Not in Bootloader Mode, or not able to communication with bootloader on port: " + options.commPort
            sys.exit(0)

    if s != None:
        print "Found Bootloader"
        print "Loading Hex File: " + options.hexFile
        hexFileHandler = file(options.hexFile,'r')
        allHex = hexFileHandler.readlines()
        hexFileHandler.close()
        extAddr = 0
        print "Loading Hex File Complete."
        print "Erasing User Program Space on MCU..."
        eraseSpace(s)
        print "Erasing Complete."
        print "Writing Program Data...."
        writeProgram(s, allHex, options.ignoreStart)
        print 'Writing Program Complete.'
        if options.readVerify == '1':
            print 'Verifying Programmed Data....'
            errCnt = verifyProgram(s,allHex)
            if errCnt == 0:
                print 'Verifying Complete, There were no Errors Found'
            else:
                print 'There were ' + str(errCnt) + ' Errors found, try reprogramming.'
                sys.exit(0)

        print "Programming Complete."
    else:
        print "Not in Bootloader Mode, or not able to communicate with bootloader!"
        sys.exit(0)



if __name__ == '__main__':
    parser = OptionParser()
    addCommandLineOptions(parser)
    options, args = parser.parse_args()
    result = pyBootProgram(options)
    sys.exit(result)
