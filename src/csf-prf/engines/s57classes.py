import re
import os
import traceback
import ctypes
from ctypes import c_char, c_int32, c_uint32, sizeof, c_ubyte

try:
    from collections import OrderedDict
except:
    from _ordereddict import ordereddict as OrderedDict
from HSTB.ecs import s57fields


# -----------------------------------------------------------------
# Code that used to live in NOAAcarto -- These are "better" s57fields values, user modifiable via the CSV files
#  Need the attributes for enforcing encoding rules in the s57 spec
# -----------------------------------------------------------------


def remove_insignificant_zeros(s):
    while "." in s and (s[-1] in ".0"):
        s = s[:-1]
    return s


# IHO Transfer Standard for Digital Hydrographic Data (IHO S-57)
import csv

# p=csv.parser() #old csv module
s57objectcat = {}
s57objectclasses = {}
s57classcodes = {}
s57attributes = {}
s57attributecodes = {}
s57expectedinput = {}
s57noaafeatures = {}
s57producers = {}


def LoadS57Objects(pathToS57=None):
    """
    pathToS57 defaults to 'os.path.split(__file__)[0]+"/forms"' if set == None
    s57objectcat={}     # {oAcronym: [oAcronymName,[oPrimitives]]}
    s57objectclasses={} # {oAcronym: [oCode,oAcronymName]}
    s57attributes={}    # {aAcronym: [aCode,aAcronymName,aType,aUnit]}
    s57expectedinput={} # {aCode: [iID+':'+iCodeName]}
    s57noaafeatures={}  # {oAcronym: [[oMandatoryAttr],[oAddlAttr],[oNonStdAttr]]}
    s57producers={}     # {code: [producerAbbr,producerName]}
    """
    if pathToS57 == None:
        pathToS57 = os.path.split(__file__)[0]
        if not pathToS57:
            pathToS57 = "."  # when main program there is not necessarily path info
        pathToS57 += "/forms"
    fyle = open(pathToS57 + "/s57objectclasses.csv")
    s57objectcat.clear()  # if call LoadS57Objects() outside of NOAAcarto
    s57objectclasses.clear()  # ibid.
    s57classcodes.clear()
    try:
        r = csv.reader(fyle)
        line = next(r)  # skip header
        line = next(r)
        while line:
            oCode, (oObjectClass, oAcronym), oPrimitives, oClass = (
                line[0].strip(),
                [sVal.strip() for sVal in line[1:3]],
                [sVal.strip() for sVal in line[-1].split(";") if sVal.strip()],
                line[-2].strip(),
            )
            # oCode,oObjectClass,oAcronym=line[:3]
            # s57objectclasses[oAcronym.strip()]=[oCode.strip(),oObjectClass.strip()]
            s57objectcat[oAcronym] = [oObjectClass, oPrimitives, oClass]
            s57objectclasses[oAcronym] = [oCode, oObjectClass]
            s57classcodes[oCode] = [oAcronym, oObjectClass]
            line = next(r)
    except StopIteration:
        pass  # hit eof
    fyle.close()

    fyle = open(pathToS57 + "/s57attributes.csv")
    s57attributes.clear()  # if call LoadS57Objects() outside of NOAAcarto
    try:
        r = csv.reader(fyle)
        line = next(r)  # skip header
        line = next(r)
        while line:
            aCode, aAttribute, aAcronym, aType, aClass, aUnit = line[:6]
            s57attributes[aAcronym.strip()] = [
                aCode.strip(),
                aAttribute.strip(),
                aType.strip(),
                aUnit,
            ]
            s57attributecodes[int(aCode.strip())] = [
                aAcronym.strip(),
                aAttribute.strip(),
                aType.strip(),
                aUnit,
            ]
            line = next(r)
    except StopIteration:
        pass  # hit eof
    fyle.close()
    fyle = open(pathToS57 + "/s57expectedinput.csv")
    s57expectedinput.clear()  # if call LoadS57Objects() outside of NOAAcarto
    try:
        r = csv.reader(fyle)
        line = next(r)  # skip header
        line = next(r)
        while line:
            fields = line[:3]
            iCode, iID = fields[:2]
            if len(fields) < 3:
                iMeaning = ""
            else:
                iMeaning = fields[-1]
            if iCode not in s57expectedinput:
                s57expectedinput[iCode] = []
            s57expectedinput[iCode.strip()].append(iID.strip() + ":" + iMeaning.strip())
            line = next(r)
    except StopIteration:
        pass  # hit eof
    fyle.close()

    fyle = open(pathToS57 + "/s57noaafeatures.csv")
    s57noaafeatures.clear()  # if call LoadS57Objects() outside of NOAAcarto
    # assumption:  first line contains just fieldnames, beginning on appropriate column
    # -and fields are, resp.: object class acronym followed by mandatory, add'l, and non-std attribute acronyms in use
    try:
        r = csv.reader(fyle)
        fields = next(r)  # header
        fieldnames = [nameStr for nameStr in fields if nameStr != ""]
        oAcronymIdx = fields.index(fieldnames[0])  # 'S-57 OBJECT ACRONYM',
        oAddlAttrIdx = fields.index(fieldnames[2])  # 'ADDITIONAL ATTRIBUTES', &
        oNonStdAttrIdx = fields.index(
            fieldnames[3]
        )  # 'NON-STANDARD ATTRIBUTES' at time of writing (skipped 'MANDATORY ATTRIBUTES' name)
        fields = next(r)
        while fields:
            oAcronym = fields[0]
            if oAcronym.strip():
                oMandatoryAttr = [
                    attrStr.strip()
                    for attrStr in [
                        acronymStr
                        for acronymStr in fields[1:oAddlAttrIdx]
                        if acronymStr != ""
                    ]
                ]
                oAddlAttr = [
                    attrStr.strip()
                    for attrStr in [
                        acronymStr
                        for acronymStr in fields[oAddlAttrIdx:oNonStdAttrIdx]
                        if acronymStr != ""
                    ]
                ]
                oNonStdAttr = [
                    attrStr.strip()
                    for attrStr in [
                        acronymStr
                        for acronymStr in fields[oNonStdAttrIdx:]
                        if acronymStr != ""
                    ]
                ]
                s57noaafeatures[oAcronym.strip()] = [
                    oMandatoryAttr,
                    oAddlAttr,
                    oNonStdAttr,
                ]
            fields = next(r)
    except StopIteration:
        pass  # hit eof
    fyle.close()

    # {code: [producerAbbr,producerName]}
    s57producers.clear()  # if call LoadS57Objects() outside of NOAAcarto
    for producersFilename in ("s57HOproducers.txt", "s57nonHOproducers.txt"):
        fyle = open(pathToS57 + "/%s" % producersFilename)
        for producerAbbr, codeStr, producerName in [
            [valStr.strip("\n").strip('"') for valStr in lineStr.split('","')]
            for lineStr in fyle.readlines()
        ]:
            s57producers[int(codeStr)] = [producerAbbr, producerName]
        fyle.close()


LoadS57Objects()
# -----------------------------------------------------------------
# END -- Code that used to live in NOAAcarto
# -----------------------------------------------------------------


# note about lexical levels/character sets
"""
2.4 Use of character sets
The default character set which must be used for all non-binary data elements (e.g. numbers, dates, text
strings etc.) is that defined by ISO/IEC 8211 (i.e. ASCII, IRV of ISO/IEC 646). Some text string subfields
may be encoded using an alternate character set. For this purpose two text string domain types are
defined. These are "Basic Text" (used to encode alphanumeric identifiers, etc.) and "General Text" to
handle certain attribute values (e.g. place names including accents and special characters).

Three lexical levels are defined for the encoding of these text string domains.
Level 0 ASCII text, IRV of ISO/IEC 646
Level 1 ISO 8859 part 1, Latin alphabet 1 repertoire (i.e. Western European Latin alphabet based languages.
Level 2 Universal Character Set repertoire UCS-2 implementation level 1 (no combining characters), Base Multilingual
plane of ISO/IEC 10646 (i.e. including Latin alphabet, Greek, Cyrillic, Arabic, Chinese, Japanese etc.)

table 2.3
"""

# Note about field termination:
"""
A Variable length subfield must be terminated by the "Unit Terminator" (UT). A variable length subfield is
specified in the data structure by a format indicator without an extent (see clause 7.2.2.1). All S-57 fields
(ISO/IEC 8211 data fields) must be terminated by the "Field Terminator" (FT).

When an alternate character set is used for a S-57 field, the UT and FT must be encoded at the lexical
level specified for that field. Table 2.4 defines the terminators for each level.

Lexical level UT FT
level 0 (1/15) (1/14)
level 1 (1/15) (1/14)
level 2 (0/0) (1/15) (0/0) (1/14)
"""

UT = 0x1F
FT = 0x1E

# Note about Floating Point Values:
"""2.6 Floating point values
Inspite of standards for the handling of binary encoded floating point values, different computer platforms
often interpret floating point values differently. To avoid such problems, all floating point values in the
binary implementation must be encoded as integers. In order to convert between the floating point and
integer value, a multiplication factor is used. For coordinate and 3-D (sounding) values the multiplication
factor is defined globally (see clause 3.2 and 3.3). Specific multiplication factors are defined on a per field
basis for all other floating point values.

Encoding of floating point values is defined by the following algorithm:

integer value = floating point value * multiplication factor

The use of a multiplication factor for floating point values in the ASCII implementation is not mandatory;
all floating point values can be encoded as R-types (see clause 7.2.2.1). If the multiplication factor is not
used, its value must be set to 1.
"""

# ProductSpec about Floating points and units
"""4.4 Units
Units to be used in an ENC are :
 Position : latitude and longitude in decimal degrees (converted into integer values, see below).
 Depth : metres.
 Height : metres.
 Positional accuracy: metres.
 Distance : nautical miles and decimal miles, or metres as defined in the IHO Object Catalogue (see
S-57, Appendix A ).

The default values for depth units, height units and positional accuracy units are encoded in the AUnits of
Depth Measurement@ [DUNI], AUnits of Height Measurement@ [HUNI] and AUnits of Positional Accuracy@
[PUNI] subfields in the AData Set Parameter@ [DSPM] field.

Latitude and longitude values are converted from decimal degrees to integers by means of the
ACoordinate Multiplication Factor@ [COMF] subfield value in the AData Set Parameter@ [DSPM] field. The
integer values are encoded in the ACoordinate in Y-axis@ [YCOO] subfield and the ACoordinate in X-axis@
[XCOO] subfield. The number of decimal digits is chosen by the data producer and is valid through out
the data set.

E.g. : If the producer chooses a resolution of 0.0001E (10-4), then the value of COMF is 10 000 (104).
A longitude = 34.5678E is converted into XCOO = longitude * COMF = 34.5678*10 000 = 345678.
The integer value of the converted coordinate is encoded in binary form.

Depths are converted from decimal meters to integers by means of the A3-D (Sounding) Multiplication
Factor@ [SOMF] subfield value in the AData Set Parameter@ [DSPM] field. The integer values are encoded
in the A3-D (Sounding) Value@ [VE3D] subfield. Soundings are never encoded with a resolution greater
than one decimeter, so the value of SOMF must be 10 encoded in binary form.
"""

domains = """
(bt)|  #Basic text (see clause 2.4)
(gt)|  # General text (see clause 2.4)
(dg)|  # digits; 0-9, right-adjusted and zero filled left (e.g. A(2) "03")
(date)| # a date subfield in the form: YYYYMMDD (e.g. "19960101")
(int)|  # integer; ISO 6093 NR1, SPACE, "+", "-", 0-9, right-adjusted and zero filled left (e.g. I(5) 00015)
(real)| # real number; ISO 6093 NR2, SPACE, "+", "-", ".", 0-9
(an)|  # alphanumerics; A-Z, a-z, 0-9, "*", "?"
(hex)|  # hexadecimals; A-F, 0-9
(ISO)  #For Format "@" there is no domain, but the comment starts with ISO -- so we'll pick that up
"""
formats = """
(A\s*\([\s\d]*\))| # *) Character data  e.g. A(5)
(I\s*\([\s\d]*\))| # *) Implicit point representation
(R\s*\([\s\d]*\))| # *) Explicit point representation
(B\s*\([\s\d]*\))| # **) Bit string
(@)| #subfield label is a row heading for a 2-D array or table of known length
(b1\d)| #b1w 1,2,4 ***) unsigned integer
(b2\d) #b2w 1,2,4 ***) signed integer
"""
# notes for formats
"""
*) An extent of X(n) indicates a fixed length subfield of length n (in bytes). An extent of X( ) indicates a variable length subfield
terminated by the appropriate delimiter (see clause 2.5).
**) The width of a fixed length bit subfield must be specified in bits. If necessary, the last byte of a fixed length bit subfield must
be filled on the right with binary zeros.
***) In the binary form, numerical data forms are constrained by the precision of the ISO/IEC 8211 binary format
"""
p1 = r"(?P<Subfield>.*?)"
p2 = r"(?P<Label>[A-Z0-9]{4})\s+"
p3 = r"(?P<FormatAscii>%s)[*)\s]+" % formats
p4 = r"(?P<FormatBin>%s?)[*)\s]*" % formats
p5 = r"(?P<domain>%s)\s*" % domains
p6 = r"(?P<spec>.*)"
subfieldpattern = p1 + p2 + p3 + p4 + p5 + p6
subfieldre = re.compile(subfieldpattern, re.VERBOSE | re.DOTALL)


# re.search(pattern, r[0], re.VERBOSE|re.DOTALL).groupdict()
# >>> re.search(r"(?P<Subfield>.*?)(?P<Label>[A-Z]{4})\s+(?P<FormatAscii>%s)[*)\s]*(?P<FormatBin>%s?)[*)\s]*(?P<domain>%s)\s*(?P<spec>.*)"%(formats, formats, s57io.domains), r[2], re.VERBOSE|re.DOTALL).groupdict()
# {'domain': 'an', 'Subfield': 'Exchange Purpose ', 'Label': 'EXPP', 'FormatAscii': 'A(1)', 'FormatBin': 'b11', 'spec': '"N" {1} - Data set is New\n"R" {2} - Data set is a revision to an existing\none'}


def BytesToStr(bytes):
    s = ""
    for b in bytes:
        s += chr(b)
    return s


def copy_to_ubytes(data, ubytes):
    if isinstance(data, str):
        data = data.encode("ISO-8859-1")
    num_bytes = len(data)
    ubytes[:num_bytes] = (ctypes.c_ubyte * num_bytes).from_buffer_copy(data)


def MakeUnion(cls):
    class MadeUnion(ctypes.Union):
        _pack_ = 1
        _fields_ = [
            (cls.__name__, cls),
            ("bytes", c_ubyte * sizeof(cls)),
        ]  # using ubyte since char gets interpreted as string and stops in the event that there is a null ("\00") character

    return MadeUnion


class S57Structure(ctypes.Structure):
    _pack_ = 1


class M(type(ctypes.Structure)):
    """This metaclass will read a "s57desc" member (doc string pretty much pulled straight from s57 docs)
    and create a subfields member that has the subfield descriptions (format, names, comments).
    It will also create a ctypes structure with all the fixed length subfields which can be accessed by
    subfield label (four letter acronym).
    """

    def __new__(cls, name, bases, classdict):
        bs57Desc = False
        try:
            s57desc = classdict["s57desc"]
            fmt = classdict["fmt"]
            bs57Desc = True
        except KeyError:
            for b in bases:
                try:
                    s57desc = b.s57desc
                    fmt = classdict["fmt"]
                    bs57Desc = True
                    break
                except:
                    pass

        if bs57Desc:
            subfields = s57desc.split("\n\n")
            classdict["subfields"] = OrderedDict()  # ordered dictionary!!!
            classdict["float_types"] = (
                []
            )  # subfields that have a Real float type and will need some conversion constant
            classdict["_fields_"] = []
            classdict["_otherfields_"] = []
            for n, s in enumerate(subfields):
                subfields[n] = s.replace("\n", "")
                # print(subfields[n])
                try:
                    groups = subfieldre.search(subfields[n]).groupdict()
                except:
                    print(subfields[n])
                    print(
                        re.search(p1, subfields[n], re.VERBOSE | re.DOTALL).groupdict()
                    )
                    print(
                        re.search(
                            p1 + p2, subfields[n], re.VERBOSE | re.DOTALL
                        ).groupdict()
                    )
                    print(
                        re.search(
                            p1 + p2 + p3, subfields[n], re.VERBOSE | re.DOTALL
                        ).groupdict()
                    )
                    print(
                        re.search(
                            p1 + p2 + p3 + p4, subfields[n], re.VERBOSE | re.DOTALL
                        ).groupdict()
                    )
                    print(
                        re.search(
                            p1 + p2 + p3 + p4 + p5, subfields[n], re.VERBOSE | re.DOTALL
                        ).groupdict()
                    )
                    print(
                        re.search(
                            p1 + p2 + p3 + p4 + p5 + p6,
                            subfields[n],
                            re.VERBOSE | re.DOTALL,
                        ).groupdict()
                    )
                # print(groups)
                # print()
                classdict["subfields"][
                    groups["Label"]
                ] = groups  # store all the format and comment info

                if (
                    classdict["fmt"] == "bin"
                ):  # for binary storage, the subfields can be ascii if no binary format is specified in the spec.
                    format = (
                        groups["FormatBin"]
                        if groups["FormatBin"]
                        else groups["FormatAscii"]
                    )
                else:
                    format = groups["FormatAscii"]
                groups["format"] = format

                acronym = (
                    "_" + groups["Label"]
                )  # prepend an underscore to the naming so that the get/set attr can find these easily.
                numbytes = re.search(r"(?P<num>\d+)", format)
                if format[0] == "b":  # b[12][124] -- e.g. b14
                    classdict["_fields_"].append((acronym, eval(format)))
                elif format[0] == "A":  # Ascii/text string
                    if numbytes:  # fixed length string
                        classdict["_fields_"].append(
                            (acronym, eval("A" + numbytes.group("num")))
                        )
                    else:  # arbitrary, delimited string
                        classdict["_otherfields_"].append(
                            [acronym, str]
                        )  # empty string for filling on read
                elif format[0] == "R":  # Real float value -- probably needs translation
                    if numbytes:  # fixed length string
                        classdict["_otherfields_"].append(
                            [acronym, eval("R" + numbytes.group("num"))]
                        )
                    else:  # arbitrary, delimited string
                        classdict["_otherfields_"].append(
                            [acronym, ascii_Real]
                        )  # empty string for filling on read
                    classdict["_otherfields_"].append(
                        ["_f" + acronym, None]
                    )  # placeholder for the converted values
                elif format[0] == "B":  # Bitfield value
                    classdict["_fields_"].append(
                        (acronym, eval("B" + numbytes.group("num")))
                    )
                elif format[0] == "I":  # ascii integer
                    if numbytes:  # fixed length string
                        classdict["_otherfields_"].append(
                            [acronym, eval("I" + numbytes.group("num"))]
                        )
                    else:  # arbitrary, delimited string
                        classdict["_otherfields_"].append(
                            [acronym, ascii_Int]
                        )  # empty string for filling on read
                elif format[0] == "@":  # unused -- multidimensional vectors
                    pass
                else:
                    print(
                        "Didn't convert -- ",
                        groups["Label"],
                        'bin="' + groups["FormatBin"] + '"',
                        groups["FormatAscii"],
                    )
                    print(subfields[n])
                    print(groups)
                    print()
                if groups["FormatAscii"][0] == "R":
                    classdict["float_types"].append(groups["Label"])
                # groups[, ctypes.c_char), ('bi',ctypes.c_int*2)]
        # print(classdict)
        return type(ctypes.Structure).__new__(cls, name, bases, classdict)


class S57BaseField(ctypes.Structure, metaclass=M):
    _bin_asc_dict = {"bin": "c", "asc": "a"}

    def __new__(cls, *args, **kwargs):
        instance = ctypes.Structure.__new__(cls, *args, **kwargs)
        for (
            acronym,
            datatype,
        ) in (
            instance._otherfields_
        ):  # instantiate the individual fields (doing this in the metaclass would make all the instances point to the same record)
            if datatype == None:
                exec("instance.%s = None" % acronym)
            else:
                exec("instance.%s = datatype()" % acronym)
        return instance

    def __init__(self, *args, **opts):
        """Passing in values in order of the subfield or by acronym name as optional arguments will fill the
        s57 object accordingly"""
        keys = list(self.subfields.keys())
        for i, v in enumerate(args):
            self.__setattr__(keys[i], v)
        for k, v in list(opts.items()):
            self.__setattr__(k, v)

    def __getattr__(
        self, key
    ):  # Get the value from the underlying subfield (perform any conversion necessary)
        # if key in s57fields.s57field_dict.keys():
        if len(key) == 4:  # try to access the subfield
            if key not in self.float_types:
                try:
                    sf = eval("self._%s" % key)
                    if isinstance(sf, str):
                        return sf
                    elif isinstance(sf, bytes):
                        return sf.decode("ISO-8859-1")
                    else:
                        return sf.val
                except AttributeError:
                    if key == "NAME":
                        u = _RCNM_RCID_NAME()
                        u.RC.RCNM.val = self._RCNM.val
                        u.RC.RCID.val = self._RCID.val
                        return u.NAME.val  # concatenated effective name
                    elif key == "RCID":
                        u = _RCNM_RCID_NAME()
                        u.NAME.val = self.NAME
                        return u.RC.RCID.val
                    elif key == "RCNM":
                        u = _RCNM_RCID_NAME()
                        u.NAME.val = self.NAME
                        return u.RC.RCNM.val
                    elif key == "LNAM":
                        return self.AGEN | self.FIDN << 16 | self.FIDS << 48
                    elif key == "FOID":
                        u = self.LNAM
                        agen = u & 0xFFFF
                        fidn = (u & 0xFFFFFFFF0000) >> 16
                        fids = (u >> 48) & 0xFFFF
                        return (agen, fidn, fids)
                    else:
                        raise AttributeError(key + " not in " + str(self.__class__))
            else:
                return eval("self._f_%s" % key)
        else:
            raise AttributeError(key + " not in " + str(self.__class__))

    def __setattr__(self, key, value):  # Set the underlying subfield value
        try:
            sf = eval("self._%s" % key)
            try:
                if key not in self.float_types:
                    if isinstance(sf, (str, bytes)):
                        if isinstance(value, bytes):  # let bytes go in directly
                            self.__dict__["_" + key] = value
                        else:  # make sure ints etc are converted to strings
                            self.__dict__["_" + key] = str(value)
                    else:
                        try:
                            sf.val = value
                        except (
                            TypeError
                        ):  # in conversion to python 3 the data is now "bytes" and strings aren't accepted by ctypes.c_char anymore
                            sf.val = value.encode("ISO-8859-1")
                else:
                    self.__dict__["_f_" + key] = value
            except:
                traceback.print_exc()
                # raise AttributeError(key+" Not set correctly")
        except:
            self.__dict__[key] = value

    def __repr__(self):
        strs = []
        for f in self.subfields:
            v = eval("self.%s" % f)
            if isinstance(v, (str)):
                strs.append(
                    f + '="%s"' % v
                )  # show strings with quotes for cut/paste utility
            else:
                strs.append(f + "=" + str(v))
        return (
            self._bin_asc_dict[self.fmt] + self.FieldTag + "(" + ", ".join(strs) + ")"
        )

    def GetInitStr(self):
        return [self.__getattr__(k) for k in list(self.subfields.keys())]

    def GetS57str(self, s57_fileobj=None):
        """Return the binary encoded s57 string with field terminator appended"""
        s = ""
        self._float_encode(
            s57_fileobj
        )  # need to prep the string or bytes for the real-float values
        for f in self.subfields:
            sf = eval("self._%s" % f)
            if isinstance(sf, str):
                s += sf + chr(UT)
            elif isinstance(sf, bytes):
                s += sf.decode("ISO-8859-1") + chr(UT)
            elif isinstance(sf, ascii_Num):
                s += sf.bytes
                if sf._maxlen_ == None:  # non-fixed length string needs a delimiter
                    s += chr(UT)
            else:
                try:
                    s += "".join([chr(v) for v in sf.bytes])
                except AttributeError as er:
                    raise er
        # s+=chr(FT) #when multiple occurances of a field are "stacked" there is no FT until after all field records are listed.
        return s

    def ReadFrom(self, data, pos=0, s57_fileobj=None):
        if isinstance(data, str):
            data = data.encode("ISO-8859-1")
        """Returns the position for byte just after the read record"""
        for f in self.subfields:
            sf = eval("self._%s" % f)
            if isinstance(sf, (str, bytes)):
                # for NATF and ATTF there is a lexical level, NALL and AALL respectively, that if set to 2 makes the End Tag four bytes instead of two
                end_tag_len = 2  # 0x1F1E
                if s57_fileobj is not None:
                    if self.FieldTag == "NATF":
                        if s57_fileobj.records[0]["DSSI"][0].NALL == 2:
                            end_tag_len = 4  # 0x001F001E
                    elif self.FieldTag == "ATTF":
                        if s57_fileobj.records[0]["DSSI"][0].AALL == 2:
                            end_tag_len = 4  # 0x001F001E
                e = data.find(UT, pos)
                if e < 0:
                    print(
                        f"{self.FieldTag} failed to find terminator UT for subfield:{f} at position:{pos}"
                    )
                    print(data)
                    # skip the remainder of the record
                    pos = len(data)
                    break
                    # raise Exception('Could not find terminator UT for string')
                else:
                    exec(
                        "self._%s = data[pos:e]" % f
                    )  # using the eval'd "sf" variable resets sf not the self._XXXX
                # print(f, "str=",sf)
                pos = e + end_tag_len - 1  # move the "file" pointer
            elif isinstance(sf, ascii_Num):
                if sf._maxlen_ != None:
                    exec("self._%s.set_string(data[pos:pos+%d])" % (f, sf._maxlen_))
                    pos += sf._maxlen_
                elif isinstance(sf, ascii_Num):
                    e = data.find(UT, pos)
                    exec(
                        "self._%s.set_string(data[pos:e])" % f
                    )  # using the eval'd "sf" variable resets sf not the self._XXXX
                    pos = e + 1  # move the "file" pointer
            else:
                copy_to_ubytes(data[pos : pos + sizeof(sf)], sf.bytes)
                # for i, v in enumerate(data[pos:pos + sizeof(sf)]):
                #     sf.bytes[i] = ord(v)
                # alternative, possible faster copy (need to determine if the string reversal [::-1] is needed
                # ctypes.memmove(sf.bytes, data[pos:pos+sizeof(sf)][::-1], sizeof(sf))
                pos += sizeof(sf)
                # print(f, sf.__class__, sf.val)
        # pos+=1 #for the end of record FT character.
        self._float_decode(
            s57_fileobj
        )  # this is really the slowdown for a lot of sounding objects.  Moved to caching COMF and SOMF in the s57io.S57File class to speed this up.
        return pos

    def _float_decode(self, s57_fileobj=None):
        pass

    def _float_encode(self, s57_fileobj=None):
        pass


class ascii_Num(object):  # remember to derive from object to use properties
    def __init__(self, value=""):
        if isinstance(value, str):
            self.set_string(value)
        else:
            self.set_num(value)

    @property
    def val(self):
        return self._v

    @property
    def bytes(self):
        return self._s

    @val.setter
    def val(self, value):
        self.set_num(value)

    @bytes.setter
    def bytes(self, value):
        self.set_string(value)

    def set_string(self, s):
        if s:
            self.set_num(self._type_(s))
        else:
            self._s = ""
            self._v = None

    def set_num(self, value):
        self._v = value
        if value is not None:
            self._s = self._fmt_ % value
            if self._maxlen_:
                if len(self._s) > self._maxlen_:
                    raise Exception("Number out of range setting ascii_num")
        else:
            self._s = ""


class ascii_Int(ascii_Num):
    _maxlen_ = None
    _fmt_ = "%d"
    _type_ = int


class ascii_Real(ascii_Num):
    _maxlen_ = None
    _fmt_ = "%f"
    _type_ = float


# --------------------------------------------------------------------------------------------------------
# Everything above this point is copied verbatim into the s57classes.py, below will be the dynamic content
# --------------------------------------------------------------------------------------------------------


class b11(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint8), ("bytes", ctypes.c_ubyte * 1)]


class b12(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint16), ("bytes", ctypes.c_ubyte * 2)]


class b14(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint32), ("bytes", ctypes.c_ubyte * 4)]


class b21(ctypes.Union):
    _fields_ = [("val", ctypes.c_int8), ("bytes", ctypes.c_ubyte * 1)]


class b22(ctypes.Union):
    _fields_ = [("val", ctypes.c_int16), ("bytes", ctypes.c_ubyte * 2)]


class b24(ctypes.Union):
    _fields_ = [("val", ctypes.c_int32), ("bytes", ctypes.c_ubyte * 4)]


class A1(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 1), ("bytes", ctypes.c_ubyte * 1)]


class R1(ascii_Real):
    _maxlen_ = 1
    _fmt_ = "%01.1f"


class I1(ascii_Int):
    _maxlen_ = 1
    _fmt_ = "%01d"


class A2(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 2), ("bytes", ctypes.c_ubyte * 2)]


class R2(ascii_Real):
    _maxlen_ = 2
    _fmt_ = "%02.1f"


class I2(ascii_Int):
    _maxlen_ = 2
    _fmt_ = "%02d"


class A3(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 3), ("bytes", ctypes.c_ubyte * 3)]


class R3(ascii_Real):
    _maxlen_ = 3
    _fmt_ = "%03.1f"


class I3(ascii_Int):
    _maxlen_ = 3
    _fmt_ = "%03d"


class A4(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 4), ("bytes", ctypes.c_ubyte * 4)]


class R4(ascii_Real):
    _maxlen_ = 4
    _fmt_ = "%04.1f"


class I4(ascii_Int):
    _maxlen_ = 4
    _fmt_ = "%04d"


class A5(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 5), ("bytes", ctypes.c_ubyte * 5)]


class R5(ascii_Real):
    _maxlen_ = 5
    _fmt_ = "%05.1f"


class I5(ascii_Int):
    _maxlen_ = 5
    _fmt_ = "%05d"


class A6(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 6), ("bytes", ctypes.c_ubyte * 6)]


class R6(ascii_Real):
    _maxlen_ = 6
    _fmt_ = "%06.1f"


class I6(ascii_Int):
    _maxlen_ = 6
    _fmt_ = "%06d"


class A7(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 7), ("bytes", ctypes.c_ubyte * 7)]


class R7(ascii_Real):
    _maxlen_ = 7
    _fmt_ = "%07.1f"


class I7(ascii_Int):
    _maxlen_ = 7
    _fmt_ = "%07d"


class A8(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 8), ("bytes", ctypes.c_ubyte * 8)]


class R8(ascii_Real):
    _maxlen_ = 8
    _fmt_ = "%08.1f"


class I8(ascii_Int):
    _maxlen_ = 8
    _fmt_ = "%08d"


class A9(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 9), ("bytes", ctypes.c_ubyte * 9)]


class R9(ascii_Real):
    _maxlen_ = 9
    _fmt_ = "%09.1f"


class I9(ascii_Int):
    _maxlen_ = 9
    _fmt_ = "%09d"


class A10(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 10), ("bytes", ctypes.c_ubyte * 10)]


class R10(ascii_Real):
    _maxlen_ = 10
    _fmt_ = "%010.1f"


class I10(ascii_Int):
    _maxlen_ = 10
    _fmt_ = "%010d"


class A11(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 11), ("bytes", ctypes.c_ubyte * 11)]


class R11(ascii_Real):
    _maxlen_ = 11
    _fmt_ = "%011.1f"


class I11(ascii_Int):
    _maxlen_ = 11
    _fmt_ = "%011d"


class A12(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 12), ("bytes", ctypes.c_ubyte * 12)]


class R12(ascii_Real):
    _maxlen_ = 12
    _fmt_ = "%012.1f"


class I12(ascii_Int):
    _maxlen_ = 12
    _fmt_ = "%012d"


class A13(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 13), ("bytes", ctypes.c_ubyte * 13)]


class R13(ascii_Real):
    _maxlen_ = 13
    _fmt_ = "%013.1f"


class I13(ascii_Int):
    _maxlen_ = 13
    _fmt_ = "%013d"


class A14(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 14), ("bytes", ctypes.c_ubyte * 14)]


class R14(ascii_Real):
    _maxlen_ = 14
    _fmt_ = "%014.1f"


class I14(ascii_Int):
    _maxlen_ = 14
    _fmt_ = "%014d"


class A15(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 15), ("bytes", ctypes.c_ubyte * 15)]


class R15(ascii_Real):
    _maxlen_ = 15
    _fmt_ = "%015.1f"


class I15(ascii_Int):
    _maxlen_ = 15
    _fmt_ = "%015d"


class A16(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 16), ("bytes", ctypes.c_ubyte * 16)]


class R16(ascii_Real):
    _maxlen_ = 16
    _fmt_ = "%016.1f"


class I16(ascii_Int):
    _maxlen_ = 16
    _fmt_ = "%016d"


class A17(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 17), ("bytes", ctypes.c_ubyte * 17)]


class R17(ascii_Real):
    _maxlen_ = 17
    _fmt_ = "%017.1f"


class I17(ascii_Int):
    _maxlen_ = 17
    _fmt_ = "%017d"


class A18(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 18), ("bytes", ctypes.c_ubyte * 18)]


class R18(ascii_Real):
    _maxlen_ = 18
    _fmt_ = "%018.1f"


class I18(ascii_Int):
    _maxlen_ = 18
    _fmt_ = "%018d"


class A19(ctypes.Union):
    _fields_ = [("val", ctypes.c_char * 19), ("bytes", ctypes.c_ubyte * 19)]


class R19(ascii_Real):
    _maxlen_ = 19
    _fmt_ = "%019.1f"


class I19(ascii_Int):
    _maxlen_ = 19
    _fmt_ = "%019d"


class _uB8(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 1)]


class B8(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 1)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB8()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B8")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB8()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _uB16(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 2)]


class B16(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 2)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB16()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B16")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB16()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _uB24(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 3)]


class B24(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 3)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB24()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B24")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB24()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _uB32(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 4)]


class B32(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 4)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB32()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B32")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB32()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _uB40(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 5)]


class B40(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 5)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB40()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B40")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB40()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _uB48(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 6)]


class B48(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 6)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB48()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B48")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB48()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _uB56(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 7)]


class B56(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 7)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB56()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B56")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB56()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _uB64(ctypes.Union):
    _fields_ = [("val", ctypes.c_uint64), ("bytes", ctypes.c_ubyte * 8)]


class B64(S57Structure):
    _fields_ = [
        ("bytes", ctypes.c_ubyte * 8)
    ]  # even using a bitfield here gives the wrong sizeof value as it returns the u64 -- 8bytes rather than the bitfield size

    def __getattr__(self, key):
        if key == "val":
            d = _uB64()
            d.bytes = self.bytes
            return d.val
        else:
            raise AttributeError("No attribute " + key + " for class B64")

    def __setattr__(self, key, value):
        if key == "val":
            d = _uB64()
            d.val = value
            copy_to_ubytes(d.bytes, self.bytes)
            # for i,n in enumerate(d.bytes): self.bytes[i] = n
        elif key == "bytes":
            raise AttributeError(
                "Can only set bytes one element at a time, use v.bytes[index] = xx"
            )
        else:
            print(key, value)
            self.__dict__[key] = value


class _RCNM_RCID(S57Structure):
    _fields_ = [("RCNM", b11), ("RCID", b14)]  # @UndefinedVariable


class _RCNM_RCID_NAME(ctypes.Union):
    _fields_ = [
        ("RC", _RCNM_RCID),
        ("NAME", B40),
        ("bytes", c_ubyte * 5),
    ]  # @UndefinedVariable


class base0001(S57BaseField):
    FieldTag = "0001"
    s57desc = """
Record Id RCID I(5) b12 int Fake record Id number as the 0001 is not described otherwise
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class c0001(base0001):
    fmt = "bin"


class a0001(base0001):
    fmt = "asc"


class baseDSID(S57BaseField):
    FieldTag = "DSID"
    s57desc = """
Record Name RCNM A(2) b11 an "DS" {10} **)

Record Identification Number RCID I(10) b14 dg Range: 1 to 232-2

Exchange Purpose EXPP A(1) b11 an "N" {1} - Data set is New
"R" {2} - Data set is a revision to an existing
one

Intended usage INTU I(1) b11 bt A numeric value indicating the intended usage for
which the data has been compiled (see Appendix
B - Product Specifications)

Data set name DSNM A( ) bt A String indicating the data set name (see
Appendix B - Product Specifications)

Edition number EDTN A( ) bt A string indicating the edition number (see
Appendix B - Product Specifications)

Update number UPDN A( ) bt A string indicating the "update number" (see
Appendix B - Product Specifications)

Update application date UADT A(8) date All updates dated on or before this date must
have been applied (see Appendix B - Product
Specifications)

Issue date ISDT A(8) date Date on which the data was made available by
the data producer (see Appendix B - Product
Specifications)

Edition number of S-57 STED R(4) real "03.1" Edition number of S-57

Product Specification PRSP A(3) b11 an "ENC" {1} Electronic Navigational Chart
"ODD" {2} IHO Object Catalogue Data
Dictionary
(see 1.4.1)

Product specification description PSDN A( ) bt A string identifying a non standard product
specification (see 1.4.1)

Product specification edition
number
PRED A( ) bt A string identifying the edition number of the
product specification (see 1.4.1)

Application profile identification PROF A(2) b11 an "EN" {1} ENC New
"ER" {2} ENC Revision
"DD" {3} IHO Data dictionary
(see 1.4.2)

Producing agency AGEN A(2) b12 an Agency code (see IHO Object Catalogue)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    def _float_decode(self, s57_fileobj=None):
        self._f_STED = float(self._STED.val)

    def _float_encode(self, s57_fileobj=None):
        # s = "%04.1f"%self._f_STED
        self._STED.val = self._f_STED


class cDSID(baseDSID):
    fmt = "bin"


class aDSID(baseDSID):
    fmt = "asc"


class baseDSSI(S57BaseField):
    FieldTag = "DSSI"
    s57desc = """
Data structure DSTR A(2) b11 an "CS" {1} Cartographic spaghetti
"CN" {2} Chain-node
"PG" {3} Planar graph
"FT" {4} Full topology
"NO" {255} Topology is not relevant
(see 3.1 and part 2 Theoretical Data Model)

ATTF lexical level AALL I(1) b11 int Lexical level used for the ATTF fields (see 2.4)

NATF lexical level NALL I(1) b11 int Lexical level used for the NATF fields (see 2.4)

Number of meta records NOMR I( ) b14 int Number of meta records in the data set

Number of cartographic records NOCR I( ) b14 int Number of cartographic records in the data set

Number of geo records NOGR I( ) b14 int Number of geo records in the data set

Number of collection records NOLR I( ) b14 int Number of collection records in the data set

Number of isolated node
records
NOIN I( ) b14 int Number of isolated node records in the data set

Number of connected node
records
NOCN I( ) b14 int Number of connected node records in the data
set

Number of edge records NOED I( ) b14 int Number of edge records in the data set

Number of face records NOFA I( ) b14 int Number of face records in the data set
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDSSI(baseDSSI):
    fmt = "bin"


class aDSSI(baseDSSI):
    fmt = "asc"


class baseDSPM(S57BaseField):
    FieldTag = "DSPM"
    s57desc = """
Record name RCNM A(2) b11 an "DP" {20}

Record identification number RCID I(10) b14 int Range: 1 to 232-2

Horizontal geodetic datum HDAT I(3) b11 int Value taken from the attribute HORDAT (see
Appendix A - Object Catalogue)

Vertical datum VDAT I(2) b11 int Value taken from the attribute VERDAT (see
Appendix A - Object Catalogue)

Sounding datum SDAT I(2) b11 int Value taken from the attribute VERDAT (see
Appendix A - Object Catalogue)

Compilation scale of data CSCL I( ) b14 int The modulus of the compilation scale. For
example, a scale of 1:25000 is encoded as 25000

Units of depth measurement DUNI I(2) b11 int Value taken from the attribute DUNITS (see
Appendix A - Object Catalogue)

Units of height measurement HUNI I(2) b11 int Value taken from the attribute HUNITS (see
Appendix A - Object Catalogue)

Units of positional accuracy PUNI I(2) b11 int Value taken from the attribute PUNITS (see
Appendix A - Object Catalogue)

Coordinate units COUN A(2) b11 an Unit of measurement for coordinates
"LL" {1} Latitude/Longitude
"EN" {2} Easting/Northing
"UC" {3} Units on the chart/map
(see 3.2.1)

Coordinate multiplication factor COMF I( ) b14 int Floating-point to integer multiplication factor for
coordinate values (see 3.2.1)

3-D (sounding) multiplication
factor
SOMF I( ) b14 int Floating point to integer multiplication factor for
3-D (sounding) values (see 3.3)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDSPM(baseDSPM):
    fmt = "bin"


class aDSPM(baseDSPM):
    fmt = "asc"


class baseDSPR(S57BaseField):
    FieldTag = "DSPR"
    s57desc = """
Projection PROJ A(3) b11 an Projection code taken from table 3.2 (see 3.2.2)

Projection parameter 1 PRP1 R( ) b24 *) real Content of parameter 1 is defined by the value of
PROJ (see 3.2.2)

Projection parameter 2 PRP2 R( ) b24 *) real Content of parameter 2 is defined by the value of
PROJ (see 3.2.2)

Projection parameter 3 PRP3 R( ) b24 *) real Content of parameter 3 is defined by the value of
PROJ (see 3.2.2)

Projection parameter 4 PRP4 R( ) b24 *) real Content of parameter 4 is defined by the value of
PROJ (see 3.2.2)

False Easting FEAS R( ) b24 *) real False easting of projection in meters (see 3.2.2)

False Northing FNOR R( ) b24 *) real False northing of projection in meters (see 3.2.2)

Floating point multiplication
factor
FPMF I( ) b14 int Floating point to integer multiplication factor for
projection parameters (see 2.6)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    def _float_decode(self, s57_fileobj=None):
        for v in ("PRP1", "PRP2", "PRP3", "PRP4", "FEAS", "FNOR"):
            exec("self._f_" + v + " = self._" + v + ".val / float(self.FPMF)")

    def _float_encode(self, s57_fileobj=None):
        for v in ("PRP1", "PRP2", "PRP3", "PRP4", "FEAS", "FNOR"):
            exec("self._" + v + ".val = int(self._f_" + v + " * self.FPMF)")


class cDSPR(baseDSPR):
    fmt = "bin"


class aDSPR(baseDSPR):
    fmt = "asc"


class baseDSRC(S57BaseField):
    FieldTag = "DSRC"
    s57desc = """
Registration point ID *RPID A(1) b11 dg Range: 1 to 9 (see 3.2.2)

Registration point Latitude or
Northing
RYCO R( ) b24 *) real Latitude or Northing of registration point.
Latitude in degrees of arc, Northing in meters
(see 3.2.2)

Registration point Longitude or
Easting
RXCO R( ) b24 *) real Longitude or Easting of registration point.
Longitude in degrees of arc, Easting in meters
(see 3.2.2)

Coordinate units for registration
point
CURP A(2) b11 an "LL" {1} Latitude and Longitude
"EN" {2} Easting and Northing

Floating point multiplication
factor
FPMF I( ) b14 int Floating point to integer multiplication factor for
Registration points RYCO and RXCO (see 2.6)

Registration point X-value RXVL R( ) b24 real Unit X-value for registration point. Floating-point
to integer conversion is defined by the COMF
subfield of the DSPM field (see 3.2.2)

Registration point Y-value RYVL R( ) b24 real Unit Y-value for registration point. Floating-point
to integer conversion is defined by the COMF
subfield of the DSPM field (see 3.2.2)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    def _float_decode(self, s57_fileobj):
        for v in ("RYCO", "RXCO"):
            exec("self._f_" + v + " = self._" + v + ".val / float(self.FPMF)")
        for v in ("RXVL", "RYVL"):
            exec(
                "self._f_" + v + " = self._" + v + ".val / float(s57_fileobj.GetCOMF())"
            )

    def _float_encode(self, s57_fileobj):
        for v in ("RYCO", "RXCO"):
            exec("self._" + v + ".val = int(self._f_" + v + " * self.FPMF)")
        for v in ("RXVL", "RYVL"):
            exec("self._" + v + ".val = int(self._f_" + v + " * s57_fileobj.GetCOMF())")


class cDSRC(baseDSRC):
    fmt = "bin"


class aDSRC(baseDSRC):
    fmt = "asc"


class baseDSHT(S57BaseField):
    FieldTag = "DSHT"
    s57desc = """
Record name RCNM A(2) b11 an "DH" {30}

Record identification number RCID I(10) b14 int Range: 1 to 232-2

Producing agency code PRCO A(2) b12 an Agency code (see IHO Object Catalogue)

Earliest source date ESDT A(8) date Date of the oldest source material within the
coverage area

Latest source date LSDT A(8) date Date of the newest source material within the
coverage area

Data collection criteria DCRT A( ) bt A string indicating the criteria used for data
collection

Compilation date CODT A(8) date Compilation date

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDSHT(baseDSHT):
    fmt = "bin"


class aDSHT(baseDSHT):
    fmt = "asc"


class baseDSAC(S57BaseField):
    FieldTag = "DSAC"
    s57desc = """
Record name RCNM A(2) b11 an "DA" {40}

Record identification number RCID I(10) b14 int Range: 1 to 232-2

Absolute positional accuracy PACC R( ) b14 *) real The best estimate of the positional accuracy of
the data. The expected input is the radius of the
two-dimensional error.

Absolute horizontal/vertical
measurement accuracy
HACC R( ) b14 *) real The best estimate of the horizontal/vertical
measurement accuracy of the data. The error is
assumed to be both positive and negative.
Subfield must be used to indicate the accuracy of
horizontal/vertical measurements. Accuracy of
soundings is encoded in the SACC subfield

Absolute sounding accuracy SACC R( ) b14 *) real The best estimate of the sounding accuracy of the
data. The error is assumed to be both positive
and negative.
Subfield must be used to indicate the vertical
accuracy of soundings. Accuracy of horizontal/
vertical measurements is encoded in the HACC
subfield.

Floating point multiplication
factor
FPMF I( ) b14 int Floating point to integer multiplication factor for
accuracy values (see 2.6)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDSAC(baseDSAC):
    fmt = "bin"


class aDSAC(baseDSAC):
    fmt = "asc"


class baseCATD(S57BaseField):
    FieldTag = "CATD"
    s57desc = """
Record name RCNM A(2) an "CD"

Record identification number RCID I(10) int Range: 1 to 232-2

File name FILE A( ) bt A string indicating a valid file name (see
Appendix B - Product Specifications)

File long name LFIL A( ) bt A string indicating the long name of the file (see
Appendix B - Product Specifications)

Volume VOLM A( ) bt A string indicating a valid volume label for the
transfer media on which the file, indicated by the
FILE subfield, is located. (see Appendix B -
Product Specifications)

Implementation IMPL A(3) an "ASC" File is a S-57 ASCII implementation
"BIN" File is a S-57 binary implementation
Codes for non ISO/IEC 8211 files within an
exchange set may be defined by a Product
Specification (see Appendix B)

Southernmost latitude SLAT R( ) real Southernmost latitude of data coverage contained
in the file indicated by the FILE subfield.
Degrees of arc, south is negative

Westernmost longitude WLON R( ) real Westernmost longitute of data coverage
contained in the file indicated by the FILE
subfield.
Degrees of arc, west is negative

Northernmost latitude NLAT R( ) real Northernmost latitude of data coverage contained
in the file indicated by the FILE subfield.
Degrees of arc, south is negative

Easternmost Longitude ELON R( ) real Easternmost longitude of data coverage
contained in the file indicated by the FILE
subfield.
Degrees of arc, west is negative

CRC CRCS A( ) hex The Cyclic Redundancy Checksum for the file
indicated by the FILE subfield (see 3.4)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    def _float_decode(self, s57_fileobj=None):
        for v in (
            "SLAT",
            "WLON",
            "NLAT",
            "ELON",
        ):  # these are floating point as strings, which can also be null strings
            exec("self._f_" + v + " = self._" + v + ".val")

    def _float_encode(self, s57_fileobj=None):
        for v in (
            "SLAT",
            "WLON",
            "NLAT",
            "ELON",
        ):  # these are floating point as strings, which can also be null strings
            exec("self._" + v + ".val = self._f_" + v)


class cCATD(baseCATD):
    fmt = "bin"


class aCATD(baseCATD):
    fmt = "asc"


class baseCATX(S57BaseField):
    FieldTag = "CATX"
    s57desc = """
Record name *RCNM A(2) b11 an "CR" {60}

Record identification number RCID I(10) b14 int Range: 1 to 232-2

Name 1 NAM1 A(12) B(40) an Foreign pointer (see 2.2)

Name 2 NAM2 A(12) B(40) an Foreign pointer (see 2.2)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cCATX(baseCATX):
    fmt = "bin"


class aCATX(baseCATX):
    fmt = "asc"


class baseDDDF(S57BaseField):
    FieldTag = "DDDF"
    s57desc = """
Record name RCNM A(2) b11 an "ID" {70}

Record identification number RCID I(10) b14 int Range: 1 to 232-2

Object or attribute OORA A(1) b11 an "A" {1} The content of OAAC/OACO is an
attribute
"O" {2} The content of OAAC/OACO is an
object

Object or attribute acronym OAAC A(6) bt A string containing an object or attribute acronym

Object or attribute label/code OACO I(5) b12 int Object or attribute label/code
1 to 8192 (IHO Object Catalogue)
8193 to 16387 (Reserved)
16388 to 65534 (General use)

Object or attribute long label OALL A( ) bt A string indicating the long label of the object or
attribute

Type of object or attribute OATY A(1) b11 an "M" {1} Meta object
"$" {2} Cartographic object
"G" {3} Geo object
"C" {4} Collection object
"F" {5} Feature attribute
"N" {6} Feature national attribute
"S" {7} Spatial attribute

Definition DEFN A( ) bt A string providing a definition of the object or
attribute

Authorizing agency AUTH A(2) b12 an Agency code (see IHO Object Catalogue)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDDDF(baseDDDF):
    fmt = "bin"


class aDDDF(baseDDDF):
    fmt = "asc"


class baseDDDR(S57BaseField):
    FieldTag = "DDDR"
    s57desc = """
Reference type *RFTP A(2) b11 an "I1" {1} INT 1 International chart 1, Symbols,
Abbreviations, Terms used on
charts
"M4" {2} M-4 Chart specifications of the IHO
and Regulations of the IHO for
international (INT) charts

Reference value RFVL A( ) bt A string containg the reference value of the type
specified in the RFTP subfield
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDDDR(baseDDDR):
    fmt = "bin"


class aDDDR(baseDDDR):
    fmt = "asc"


class baseDDDI(S57BaseField):
    FieldTag = "DDDI"
    s57desc = """
Record name RCNM A(2) b11 an "IO" {80}

Record identification number RCID I(10) b14 int Range: 1 to 232-2

Attribute label/code ATLB I(5) b12 int A valid attribute label/code

Attribute domain type ATDO A(1) b11 an "E" {1} Enumerated
"L" {2} List of enumerated values
"F" {3} Float
"I" {4} Integer
"A" {5} Code string in ASCII characters
"S" (6) Free text format

Attribute domain value
measurement unit
ADMU A( ) bt A string indicating the units of measurement for
values in the attribute domain

Attribute domain format ADFT A( ) bt A string containing an attribute format description

Authorizing agency AUTH A(2) b12 an Agency code (see IHO Object Catalogue)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDDDI(baseDDDI):
    fmt = "bin"


class aDDDI(baseDDDI):
    fmt = "asc"


class baseDDOM(S57BaseField):
    FieldTag = "DDOM"
    s57desc = """
Range or value RAVA A(1) b11 an "M" {1} DVAL contains the maximum value
"N" {2} DVAL contains the minimum value
"V" {3} DVAL contains a specific single value
from the domain of ATDO

Domain value DVAL A( ) bt A string containing a value specified by the RAVA
and ATDO subfields

Domain value short description DVSD A( ) bt A string contaning the short description of the
domain value

Domain value definition DEFN A( ) bt A string containing the definition of the domain
value

Authorizing agency AUTH A(2) b12 an Agency code (see IHO Object Catalogue)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDDOM(baseDDOM):
    fmt = "bin"


class aDDOM(baseDDOM):
    fmt = "asc"


class baseDDRF(S57BaseField):
    FieldTag = "DDRF"
    s57desc = """
Reference type *RFTP A(2) b11 an "I1" {1} INT 1 International chart 1, Symbols,
Abbreviations, Terms used on
charts
"M4" {2} M-4 Chart specifications of the IHO
and Regulations of the IHO for
international (INT) charts

Reference value RFVL A( ) bt A string containing the reference value of the type
specified in the RFTP subfield
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDDRF(baseDDRF):
    fmt = "bin"


class aDDRF(baseDDRF):
    fmt = "asc"


class baseDDSI(S57BaseField):
    FieldTag = "DDSI"
    s57desc = """
Record name RCNM A(2) b11 an "IS" {90}

Record identification number RCID I(10) b14 int Range: 1 to 232-2

Object label/code OBLB I(5) b12 int A valid object label/code
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDDSI(baseDDSI):
    fmt = "bin"


class aDDSI(baseDDSI):
    fmt = "asc"


class baseDDSC(S57BaseField):
    FieldTag = "DDSC"
    s57desc = """
Attribute label/code *ATLB I(5) b12 int A valid attribute label/code

Attribute set ASET A(1) b11 an "A" {1} Attribute set A
"B" {2} Attribute set B
"C" {3} Attribute set C

Authorizing agency AUTH A(2) b12 an Agency code (see IHO Object Catalogue)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cDDSC(baseDDSC):
    fmt = "bin"


class aDDSC(baseDDSC):
    fmt = "asc"


class baseFRID(S57BaseField):
    FieldTag = "FRID"
    s57desc = """
Record name RCNM A(2) b11 an "FE" {100}

Record identification number RCID I(10 ) b14 int Range: 1 to 232-2

Object geometric primitive PRIM A(1) b11 an "P" {1} Point
"L" {2} Line
"A" {3} Area
"N" {255} Object does not directly reference any
spatial objects
(see 4.2.1)

Group GRUP I(3) b11 int Range: 1 to 254, 255 - No group (binary)
(see Appendix B - Product Specifications)

Object label/code OBJL I(5) b12 int A valid object label/code

Record version RVER I(3) b12 int RVER contains the serial number of the record
edition (see 8.4.2.1)

Record update instruction RUIN A(1) b11 an "I" {1} Insert
"D" {2} Delete
"M" {3} Modify
(see 8.4.2.2)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cFRID(baseFRID):
    fmt = "bin"


class aFRID(baseFRID):
    fmt = "asc"


class baseFOID(S57BaseField):
    FieldTag = "FOID"
    s57desc = """
Producing agency AGEN A(2) b12 an Agency code (see 4.3)

Feature identification number FIDN I(10) b14 int Range: 1 to 232-2 (see 4.3.2)

Feature identification
subdivision
FIDS I(5) b12 int Range: 1 to 216-2 (see 4.3.2)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cFOID(baseFOID):
    fmt = "bin"


class aFOID(baseFOID):
    fmt = "asc"


class baseATTF(S57BaseField):
    FieldTag = "ATTF"
    s57desc = """
Attribute label/code *ATTL I(5) b12 int A valid attribute label/code

Attribute value ATVL A( ) gt A string containing a valid value for the domain
specified by the attribute label/code in ATTL
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    # enforce the limit on "insignificant" zeros on float values
    def __setattr__(self, key, value):
        if key == "ATVL":  # setting the value
            try:
                t = s57attributecodes[self.ATTL][2]
            except:
                t = ""
            if t == "F":  # floating point value -- remove trailing zeros
                value = remove_insignificant_zeros(str(value))
        S57BaseField.__setattr__(self, key, value)


class cATTF(baseATTF):
    fmt = "bin"


class aATTF(baseATTF):
    fmt = "asc"


class baseNATF(S57BaseField):
    FieldTag = "NATF"
    s57desc = """
Attribute label/code *ATTL I(5) b12 int A valid national attribute label/code

Attribute value ATVL A( ) gt A string containing a valid value for the domain
specified by the attribute label/code in ATTL
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cNATF(baseNATF):
    fmt = "bin"


class aNATF(baseNATF):
    fmt = "asc"


class baseFFPC(S57BaseField):
    FieldTag = "FFPC"
    s57desc = """
Feature object pointer update
instruction
FFUI A(1) b11 an "I" {1} Insert
"D" {2} Delete
"M" {3} Modify
(see 8.4.2.3)

Feature object pointer index FFIX I( ) b12 int Index (position) of the adressed record pointer
within the FFPT field(s) of the target record
(see 8.4.2.3)

Number of feature object
pointers
NFPT I( ) b12 int Number of record pointers in the FFPT field(s) of
the update record (see 8.4.2.3)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cFFPC(baseFFPC):
    fmt = "bin"


class aFFPC(baseFFPC):
    fmt = "asc"


class baseFFPT(S57BaseField):
    FieldTag = "FFPT"
    s57desc = """
Long Name *LNAM A(17) B(64) an Foreign pointer (see 4.3)

Relationship indicator RIND A( ) b11 an "M" {1} Master
"S" {2} Slave
"P" {3} Peer
Other values may be defined by the relevant
product specification
(see 6.2 and 6.3)

Comment COMT A( ) bt A string of characters
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cFFPT(baseFFPT):
    fmt = "bin"


class aFFPT(baseFFPT):
    fmt = "asc"


class baseFSPC(S57BaseField):
    FieldTag = "FSPC"
    s57desc = """
Feature to spatial record pointer
update instruction
FSUI A(1) b11 an "I" {1} Insert
"D" {2} Delete
"M" {3} Modify
(see 8.4.2.4)

Feature to spatial record pointer
index
FSIX I( ) b12 int Index (position) of the adressed record pointer
within the FSPT field(s) of the target record
(see 8.4.2.4)

Number of feature to spatial
record pointers
NSPT I( ) b12 int Number of record pointers in the FSPT field(s) of
the update record (see 8.4.2.4)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cFSPC(baseFSPC):
    fmt = "bin"


class aFSPC(baseFSPC):
    fmt = "asc"


class baseFSPT(S57BaseField):
    FieldTag = "FSPT"
    s57desc = """
Name *NAME A(12) B(40) an Foreign pointer (see 2.2)

Orientation ORNT A(1) b11 an "F" {1} Forward
"R" {2} Reverse
"N" {255} NULL

Usage indicator USAG A(1) b11 an "E" {1} Exterior
"I" {2} Interior
"C" {3} Exterior boundary truncated by the
data limit
"N" {255} NULL

Masking indicator MASK A(1) b11 an "M" {1} Mask
"S" {2} Show
"N" {255} NULL
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cFSPT(baseFSPT):
    fmt = "bin"


class aFSPT(baseFSPT):
    fmt = "asc"


class baseVRID(S57BaseField):
    FieldTag = "VRID"
    s57desc = """
Record name RCNM A(2) b11 an "VI" {110} Isolated node
"VC" {120} Connected node
"VE" {130} Edge
"VF" {140} Face

Record identification number RCID I(10 ) b14 int Range: 1 to 232-2

Record version RVER I(3) b12 int RVER contains the serial number of the record
edition (see 8.4.3.1)

Record update instruction RUIN A(1) b11 an "I" {1} Insert
"D" {2} Delete
"M" {3} Modify
(see 8.4.3.2)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cVRID(baseVRID):
    fmt = "bin"


class aVRID(baseVRID):
    fmt = "asc"


class baseATTV(S57BaseField):
    FieldTag = "ATTV"
    s57desc = """
Attribute label/code *ATTL I(5) b12 int A valid attribute label/code

Attribute value ATVL A( ) bt A string containing a valid value for the domain
specified by the attribute label/code in ATTL
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cATTV(baseATTV):
    fmt = "bin"


class aATTV(baseATTV):
    fmt = "asc"


class baseVRPC(S57BaseField):
    FieldTag = "VRPC"
    s57desc = """
Vector record pointer update
instruction
VPUI A(1) b11 an "I" {1} Insert
"D" {2} Delete
"M" {3} Modify
(see 8.4.3.2.b)

Vector record pointer index VPIX I( ) b12 int Index (position) of the adressed vector record
pointer within the VRPT field(s) of the target
record (see 8.4.3.2.b)

Number of vector record
pointers
NVPT I( ) b12 int Number of vector record pointers in the VRPT
field(s) of the update record (see 8.4.3.2.b)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cVRPC(baseVRPC):
    fmt = "bin"


class aVRPC(baseVRPC):
    fmt = "asc"


class baseVRPT(S57BaseField):
    FieldTag = "VRPT"
    s57desc = """
Name *NAME A(12) B(40) an Foreign pointer (see 2.2)

Orientation ORNT A(1) b11 an "F" {1} Forward
"R" {2} Reverse
"N" {255} NULL
(see 5.1.3)

Usage indicator USAG A(1) b11 an "E" {1} Exterior
"I" {2} Interior
"C" {3} Exterior boundary truncated by the
data limit
"N" {255} NULL
(see 5.1.3)

Topology indicator TOPI A(1) b11 an "B" {1} Beginning node
"E" {2} End node
"S" {3} Left face
"D" {4} Right face
"F" {5} Containing face
"N" {255} NULL
(see 5.1.3)

Masking indicator MASK A(1) b11 an "M" {1} Mask
"S" {2} Show
"N" {255} NULL
(see 5.1.3)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cVRPT(baseVRPT):
    fmt = "bin"


class aVRPT(baseVRPT):
    fmt = "asc"


class baseSGCC(S57BaseField):
    FieldTag = "SGCC"
    s57desc = """
Coordinate update instruction CCUI A(1) b11 an "I" {1} Insert
"D" {2} Delete
"M" {3} Modify
(see 8.4.3.3)

Coordinate index CCIX I( ) b12 int Index (position) of the adressed coordinate within
the coordinate field(s) of the target record
(see 8.4.3.3)

Number of coordinates CCNC I( ) b12 int Number of coordinates in the coordinate field(s)
of the update record (see 8.4.3.3)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cSGCC(baseSGCC):
    fmt = "bin"


class aSGCC(baseSGCC):
    fmt = "asc"


class baseSG2D(S57BaseField):
    FieldTag = "SG2D"
    s57desc = """
Coordinate in Y axis *YCOO R( ) b24 real Y coordinate. Format is specified in Appendix B -
Product Specification

Coordinate in X axis XCOO R( ) b24 real X coordinate. Format is specified in Appendix B -
Product Specification
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    def _float_decode(self, s57_fileobj):
        self._f_YCOO = self._YCOO.val / float(s57_fileobj.GetCOMF())
        self._f_XCOO = self._XCOO.val / float(s57_fileobj.GetCOMF())

    def _float_encode(self, s57_fileobj):
        self._XCOO.val = int(self._f_XCOO * s57_fileobj.GetCOMF())
        self._YCOO.val = int(self._f_YCOO * s57_fileobj.GetCOMF())


class cSG2D(baseSG2D):
    fmt = "bin"


class aSG2D(baseSG2D):
    fmt = "asc"


class baseSG3D(S57BaseField):
    FieldTag = "SG3D"
    s57desc = """
Coordinate in Y axis *YCOO R( ) b24 real Y coordinate. Format is specified in Appendix B -
Product Specifications

Coordinate in X axis XCOO R( ) b24 real X coordinate. Format is specified in Appendix B -
Product Specifications

3-D (sounding) value VE3D R( ) b24 real Value of third dimension. Content and format are
specified in Appendix B - Product Specifications
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    def _float_decode(self, s57_fileobj):
        self._f_XCOO = self._XCOO.val / float(s57_fileobj.GetCOMF())
        self._f_YCOO = self._YCOO.val / float(s57_fileobj.GetCOMF())
        self._f_VE3D = self._VE3D.val / float(s57_fileobj.GetSOMF())

    def _float_encode(self, s57_fileobj):
        self._XCOO.val = int(self._f_XCOO * s57_fileobj.GetCOMF())
        self._YCOO.val = int(self._f_YCOO * s57_fileobj.GetCOMF())
        self._VE3D.val = int(self._f_VE3D * s57_fileobj.GetSOMF())


class cSG3D(baseSG3D):
    fmt = "bin"


class aSG3D(baseSG3D):
    fmt = "asc"


class baseARCC(S57BaseField):
    FieldTag = "ARCC"
    s57desc = """
Arc/Curve type ATYP A(1) b11 an "C" {1} Arc 3 point centre
"E" {2} Elliptical arc
"U" {3} Uniform Bspline
"B" {4} Piecewise bezier
"N" {5} Non-uniform rational B-spline
(see 5.1.4.4)

Construction surface SURF A(1) b11 an "E" {1} Ellipsoidal
Object must be reconstructed prior
to projection onto a 2-D surface
"P" {2} Planar
Object must be reconstructed after
projection onto a 2-D surface,
regardless of projection used

Curve order ORDR I(1) b11 int Value of the largest exponent of the polynomial
equation
Range: 1 to 9

Interpolated point resolution RESO R( ) b14 *) real Spacing along line path between interpolated
points. Value in map units (millimeters)

Floating point multiplication
factor
FPMF I( ) b14 int Floating point to integer multiplication factor for
interpolated point resolution value (see 2.6)
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)

    def _float_decode(self, s57_fileobj=None):
        for v in ("PACC", "HACC", "SACC"):
            exec("self._f_" + v + " = self._" + v + ".val / float(self.FPMF)")

    def _float_encode(self, s57_fileobj=None):
        for v in ("PACC", "HACC", "SACC"):
            exec("self._" + v + ".val = int(self._f_" + v + " * self.FPMF)")


class cARCC(baseARCC):
    fmt = "bin"


class aARCC(baseARCC):
    fmt = "asc"


class baseAR2D(S57BaseField):
    FieldTag = "AR2D"
    s57desc = """
Start point STPT @ ISO/IEC 8211 Cartesian label

Centre point CTPT @ ISO/IEC 8211 Cartesian label

End point ENPT @ ISO/IEC 8211 Cartesian label

Coordinate in Y axis *YCOO R( ) b24 real Y coordinate. Format is specified in Appendix B -
Product Specifications

Coordinate in X axis XCOO R( ) b24 real X coordinate. Format is specified in Appendix B -
Product Specifications
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cAR2D(baseAR2D):
    fmt = "bin"


class aAR2D(baseAR2D):
    fmt = "asc"


class baseEL2D(S57BaseField):
    FieldTag = "EL2D"
    s57desc = """
Start point STPT @ ISO/IEC 8211 Cartesian label

Centre point CTPT @ ISO/IEC 8211 Cartesian label

End point ENPT @ ISO/IEC 8211 Cartesian label

Conjugate diameter point
major axis
CDPM @ ISO/IEC 8211 Cartesian label

Conjugate diameter point
minor axis
CDPR @ ISO/IEC 8211 Cartesian label

Coordinate in Y axis *YCOO R( ) b24 real Y coordinate. Format is specified in Appendix B -
Product Specifications

Coordinate in X axis XCOO R( ) b24 real X coordinate. Format is specified in Appendix B -
Product Specifications
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cEL2D(baseEL2D):
    fmt = "bin"


class aEL2D(baseEL2D):
    fmt = "asc"


class baseCT2D(S57BaseField):
    FieldTag = "CT2D"
    s57desc = """
Coordinate in Y axis *YCOO R( ) b24 real Y coordinate. Format is specified in Appendix B -
Product Specifications

Coordinate in X axis XCOO R( ) b24 real X coordinate. Format is specified in Appendix B -
Product Specifications
"""

    def __init__(self, *args, **opts):
        S57BaseField.__init__(self, *args, **opts)


class cCT2D(baseCT2D):
    fmt = "bin"


class aCT2D(baseCT2D):
    fmt = "asc"


ob_classes = {
    "ADMARE": (1, "Administration area (Named)"),
    "AIRARE": (2, "Airport / airfield"),
    "ACHBRT": (3, "Anchor berth"),
    "ACHARE": (4, "Anchorage area"),
    "BCNCAR": (5, "Beacon, cardinal"),
    "BCNISD": (6, "Beacon, isolated danger"),
    "BCNLAT": (7, "Beacon, lateral"),
    "BCNSAW": (8, "Beacon, safe water"),
    "BCNSPP": (9, "Beacon, special purpose/general"),
    "BERTHS": (10, "Berth"),
    "BRIDGE": (11, "Bridge"),
    "BUISGL": (12, "Building, single"),
    "BUAARE": (13, "Built-up area"),
    "BOYCAR": (14, "Buoy, cardinal"),
    "BOYINB": (15, "Buoy, installation"),
    "BOYISD": (16, "Buoy, isolated danger"),
    "BOYLAT": (17, "Buoy, lateral"),
    "BOYSAW": (18, "Buoy, safe water"),
    "BOYSPP": (19, "Buoy, special purpose/general"),
    "CBLARE": (20, "Cable area"),
    "CBLOHD": (21, "Cable, overhead"),
    "CBLSUB": (22, "Cable, submarine"),
    "CANALS": (23, "Canal"),
    "CANBNK": (24, "Canal bank"),
    "CTSARE": (25, "Cargo transshipment area"),
    "CAUSWY": (26, "Causeway"),
    "CTNARE": (27, "Caution area"),
    "CHKPNT": (28, "Checkpoint"),
    "CGUSTA": (29, "Coastguard station"),
    "COALNE": (30, "Coastline"),
    "CONZNE": (31, "Contiguous zone"),
    "COSARE": (32, "Continental shelf area"),
    "CTRPNT": (33, "Control point"),
    "CONVYR": (34, "Conveyor"),
    "CRANES": (35, "Crane"),
    "CURENT": (36, "Current - non - gravitational"),
    "CUSZNE": (37, "Custom zone"),
    "DAMCON": (38, "Dam"),
    "DAYMAR": (39, "Daymark"),
    "DWRTCL": (40, "Deep water route centerline"),
    "DWRTPT": (41, "Deep water route part"),
    "DEPARE": (42, "Depth area"),
    "DEPCNT": (43, "Depth contour"),
    "DISMAR": (44, "Distance mark"),
    "DOCARE": (45, "Dock area"),
    "DRGARE": (46, "Dredged area"),
    "DRYDOC": (47, "Dry dock"),
    "DMPGRD": (48, "Dumping ground"),
    "DYKCON": (49, "Dyke"),
    "EXEZNE": (50, "Exclusive Economic Zone"),
    "FAIRWY": (51, "Fairway"),
    "FNCLNE": (52, "Fence/wall"),
    "FERYRT": (53, "Ferry route"),
    "FSHZNE": (54, "Fishery zone"),
    "FSHFAC": (55, "Fishing facility"),
    "FSHGRD": (56, "Fishing ground"),
    "FLODOC": (57, "Floating dock"),
    "FOGSIG": (58, "Fog signal"),
    "FORSTC": (59, "Fortified structure"),
    "FRPARE": (60, "Free port area"),
    "GATCON": (61, "Gate"),
    "GRIDRN": (62, "Gridiron"),
    "HRBARE": (63, "Harbour area (administrative)"),
    "HRBFAC": (64, "Harbour facility"),
    "HULKES": (65, "Hulk"),
    "ICEARE": (66, "Ice area"),
    "ICNARE": (67, "Incineration area"),
    "ISTZNE": (68, "Inshore traffic zone"),
    "LAKARE": (69, "Lake"),
    "LAKSHR": (70, "Lake shore"),
    "LNDARE": (71, "Land area"),
    "LNDELV": (72, "Land elevation"),
    "LNDRGN": (73, "Land region"),
    "LNDMRK": (74, "Landmark"),
    "LIGHTS": (75, "Light"),
    "LITFLT": (76, "Light float"),
    "LITVES": (77, "Light vessel"),
    "LOCMAG": (78, "Local magnetic anomaly"),
    "LOKBSN": (79, "Lock basin"),
    "LOGPON": (80, "Log pond"),
    "MAGVAR": (81, "Magnetic variation"),
    "MARCUL": (82, "Marine farm/culture"),
    "MIPARE": (83, "Military practice area"),
    "MORFAC": (84, "Mooring/warping facility"),
    "NAVLNE": (85, "Navigation line"),
    "OBSTRN": (86, "Obstruction"),
    "OFSPLF": (87, "Offshore platform"),
    "OSPARE": (88, "Offshore production area"),
    "OILBAR": (89, "Oil barrier"),
    "PILPNT": (90, "Pile"),
    "PILBOP": (91, "Pilot boarding place"),
    "PIPARE": (92, "Pipeline area"),
    "PIPOHD": (93, "Pipeline, overhead"),
    "PIPSOL": (94, "Pipeline, submarine/on land"),
    "PONTON": (95, "Pontoon"),
    "PRCARE": (96, "Precautionary area"),
    "PRDARE": (97, "Production / storage area"),
    "PYLONS": (98, "Pylon/bridge support"),
    "RADLNE": (99, "Radar line"),
    "RADRNG": (100, "Radar range"),
    "RADRFL": (101, "Radar reflector"),
    "RADSTA": (102, "Radar station"),
    "RTPBCN": (103, "Radar transponder beacon"),
    "RDOCAL": (104, "Radio calling-in point"),
    "RDOSTA": (105, "Radio station"),
    "RAILWY": (106, "Railway"),
    "RAPIDS": (107, "Rapids"),
    "RCRTCL": (108, "Recommended route centerline"),
    "RECTRC": (109, "Recommended track"),
    "RCTLPT": (110, "Recommended Traffic Lane Part"),
    "RSCSTA": (111, "Rescue station"),
    "RESARE": (112, "Restricted area"),
    "RETRFL": (113, "Retro-reflector"),
    "RIVERS": (114, "River"),
    "RIVBNK": (115, "River bank"),
    "ROADWY": (116, "Road"),
    "RUNWAY": (117, "Runway"),
    "SNDWAV": (118, "Sand waves"),
    "SEAARE": (119, "Sea area / named water area"),
    "SPLARE": (120, "Sea-plane landing area"),
    "SBDARE": (121, "Seabed area"),
    "SLCONS": (122, "Shoreline Construction"),
    "SISTAT": (123, "Signal station, traffic"),
    "SISTAW": (124, "Signal station, warning"),
    "SILTNK": (125, "Silo / tank"),
    "SLOTOP": (126, "Slope topline"),
    "SLOGRD": (127, "Sloping ground"),
    "SMCFAC": (128, "Small craft facility"),
    "SOUNDG": (129, "Sounding"),
    "SPRING": (130, "Spring"),
    "SQUARE": (131, "Square"),
    "STSLNE": (132, "Straight territorial sea baseline"),
    "SUBTLN": (133, "Submarine transit lane"),
    "SWPARE": (134, "Swept Area"),
    "TESARE": (135, "Territorial sea area"),
    "TS_PRH": (136, "Tidal stream - harmonic prediction"),
    "TS_PNH": (137, "Tidal stream - non-harmonic prediction"),
    "TS_PAD": (138, "Tidal stream panel data"),
    "TS_TIS": (139, "Tidal stream - time series"),
    "T_HMON": (140, "Tide - harmonic prediction"),
    "T_NHMN": (141, "Tide - non-harmonic prediction"),
    "T_TIMS": (142, "Tidal stream - time series"),
    "TIDEWY": (143, "Tideway"),
    "TOPMAR": (144, "Top mark"),
    "TSELNE": (145, "Traffic Separation Line"),
    "TSSBND": (146, "Traffic Separation Scheme  Boundary"),
    "TSSCRS": (147, "Traffic Separation Scheme Crossing"),
    "TSSLPT": (148, "Traffic Separation Scheme  Lane part"),
    "TSSRON": (149, "Traffic Separation Scheme  Roundabout"),
    "TSEZNE": (150, "Traffic Separation Zone"),
    "TUNNEL": (151, "Tunnel"),
    "TWRTPT": (152, "Two-way route  part"),
    "UWTROC": (153, "Underwater rock / awash rock"),
    "UNSARE": (154, "Unsurveyed area"),
    "VEGATN": (155, "Vegetation"),
    "WATTUR": (156, "Water turbulence"),
    "WATFAL": (157, "Waterfall"),
    "WEDKLP": (158, "Weed/Kelp"),
    "WRECKS": (159, "Wreck"),
    "TS_FEB": (160, "Tidal stream - flood/ebb"),
    "ARCSLN": (161, "Archipelagic Sea Lane"),
    "ASLXIS": (162, "Archipelagic Sea Lane Axis"),
    "NEWOBJ": (163, "New Object"),
    "M_ACCY": (300, "Accuracy of data"),
    "M_CSCL": (301, "Compilation scale of data"),
    "M_COVR": (302, "Coverage"),
    "M_HDAT": (303, "Horizontal datum of data"),
    "M_HOPA": (304, "Horizontal datum shift parameters"),
    "M_NPUB": (305, "Nautical publication information"),
    "M_NSYS": (306, "Navigational system of marks"),
    "M_PROD": (307, "Production information"),
    "M_QUAL": (308, "Quality of data"),
    "M_SDAT": (309, "Sounding datum"),
    "M_SREL": (310, "Survey reliability"),
    "M_UNIT": (311, "Units of measurement of data"),
    "M_VDAT": (312, "Vertical datum of data"),
    "m_pyup": (313, "Pydro update data"),
    "C_AGGR": (400, "Aggregation"),
    "C_ASSO": (401, "Association"),
    "C_STAC": (402, "Stacked on/stacked under"),
    "$AREAS": (500, "Cartographic area"),
    "$LINES": (501, "Cartographic line"),
    "$CSYMB": (502, "Cartographic symbol"),
    "$COMPS": (503, "Compass"),
    "$TEXTS": (504, "Text"),
    "cvrage": (644, "Coverage Area"),
    "brklne": (696, "Breakline"),
    "usrmrk": (11001, "User marker"),
    "survey": (11003, "Survey project"),
    "surfac": (11004, "Bathymetric surface"),
    "prodpf": (11008, "Product Profile"),
}
class_codes = {
    1: ("ADMARE", "Administration area (Named)"),
    2: ("AIRARE", "Airport / airfield"),
    3: ("ACHBRT", "Anchor berth"),
    4: ("ACHARE", "Anchorage area"),
    5: ("BCNCAR", "Beacon, cardinal"),
    6: ("BCNISD", "Beacon, isolated danger"),
    7: ("BCNLAT", "Beacon, lateral"),
    8: ("BCNSAW", "Beacon, safe water"),
    9: ("BCNSPP", "Beacon, special purpose/general"),
    10: ("BERTHS", "Berth"),
    11: ("BRIDGE", "Bridge"),
    12: ("BUISGL", "Building, single"),
    13: ("BUAARE", "Built-up area"),
    14: ("BOYCAR", "Buoy, cardinal"),
    15: ("BOYINB", "Buoy, installation"),
    16: ("BOYISD", "Buoy, isolated danger"),
    17: ("BOYLAT", "Buoy, lateral"),
    18: ("BOYSAW", "Buoy, safe water"),
    19: ("BOYSPP", "Buoy, special purpose/general"),
    20: ("CBLARE", "Cable area"),
    21: ("CBLOHD", "Cable, overhead"),
    22: ("CBLSUB", "Cable, submarine"),
    23: ("CANALS", "Canal"),
    24: ("CANBNK", "Canal bank"),
    25: ("CTSARE", "Cargo transshipment area"),
    26: ("CAUSWY", "Causeway"),
    27: ("CTNARE", "Caution area"),
    28: ("CHKPNT", "Checkpoint"),
    29: ("CGUSTA", "Coastguard station"),
    30: ("COALNE", "Coastline"),
    31: ("CONZNE", "Contiguous zone"),
    32: ("COSARE", "Continental shelf area"),
    33: ("CTRPNT", "Control point"),
    34: ("CONVYR", "Conveyor"),
    35: ("CRANES", "Crane"),
    36: ("CURENT", "Current - non - gravitational"),
    37: ("CUSZNE", "Custom zone"),
    38: ("DAMCON", "Dam"),
    39: ("DAYMAR", "Daymark"),
    40: ("DWRTCL", "Deep water route centerline"),
    41: ("DWRTPT", "Deep water route part"),
    42: ("DEPARE", "Depth area"),
    43: ("DEPCNT", "Depth contour"),
    44: ("DISMAR", "Distance mark"),
    45: ("DOCARE", "Dock area"),
    46: ("DRGARE", "Dredged area"),
    47: ("DRYDOC", "Dry dock"),
    48: ("DMPGRD", "Dumping ground"),
    49: ("DYKCON", "Dyke"),
    50: ("EXEZNE", "Exclusive Economic Zone"),
    51: ("FAIRWY", "Fairway"),
    52: ("FNCLNE", "Fence/wall"),
    53: ("FERYRT", "Ferry route"),
    54: ("FSHZNE", "Fishery zone"),
    55: ("FSHFAC", "Fishing facility"),
    56: ("FSHGRD", "Fishing ground"),
    57: ("FLODOC", "Floating dock"),
    58: ("FOGSIG", "Fog signal"),
    59: ("FORSTC", "Fortified structure"),
    60: ("FRPARE", "Free port area"),
    61: ("GATCON", "Gate"),
    62: ("GRIDRN", "Gridiron"),
    63: ("HRBARE", "Harbour area (administrative)"),
    64: ("HRBFAC", "Harbour facility"),
    65: ("HULKES", "Hulk"),
    66: ("ICEARE", "Ice area"),
    67: ("ICNARE", "Incineration area"),
    68: ("ISTZNE", "Inshore traffic zone"),
    69: ("LAKARE", "Lake"),
    70: ("LAKSHR", "Lake shore"),
    71: ("LNDARE", "Land area"),
    72: ("LNDELV", "Land elevation"),
    73: ("LNDRGN", "Land region"),
    74: ("LNDMRK", "Landmark"),
    75: ("LIGHTS", "Light"),
    76: ("LITFLT", "Light float"),
    77: ("LITVES", "Light vessel"),
    78: ("LOCMAG", "Local magnetic anomaly"),
    79: ("LOKBSN", "Lock basin"),
    80: ("LOGPON", "Log pond"),
    81: ("MAGVAR", "Magnetic variation"),
    82: ("MARCUL", "Marine farm/culture"),
    83: ("MIPARE", "Military practice area"),
    84: ("MORFAC", "Mooring/warping facility"),
    85: ("NAVLNE", "Navigation line"),
    86: ("OBSTRN", "Obstruction"),
    87: ("OFSPLF", "Offshore platform"),
    88: ("OSPARE", "Offshore production area"),
    89: ("OILBAR", "Oil barrier"),
    90: ("PILPNT", "Pile"),
    91: ("PILBOP", "Pilot boarding place"),
    92: ("PIPARE", "Pipeline area"),
    93: ("PIPOHD", "Pipeline, overhead"),
    94: ("PIPSOL", "Pipeline, submarine/on land"),
    95: ("PONTON", "Pontoon"),
    96: ("PRCARE", "Precautionary area"),
    97: ("PRDARE", "Production / storage area"),
    98: ("PYLONS", "Pylon/bridge support"),
    99: ("RADLNE", "Radar line"),
    100: ("RADRNG", "Radar range"),
    101: ("RADRFL", "Radar reflector"),
    102: ("RADSTA", "Radar station"),
    103: ("RTPBCN", "Radar transponder beacon"),
    104: ("RDOCAL", "Radio calling-in point"),
    105: ("RDOSTA", "Radio station"),
    106: ("RAILWY", "Railway"),
    107: ("RAPIDS", "Rapids"),
    108: ("RCRTCL", "Recommended route centerline"),
    109: ("RECTRC", "Recommended track"),
    110: ("RCTLPT", "Recommended Traffic Lane Part"),
    111: ("RSCSTA", "Rescue station"),
    112: ("RESARE", "Restricted area"),
    113: ("RETRFL", "Retro-reflector"),
    114: ("RIVERS", "River"),
    115: ("RIVBNK", "River bank"),
    116: ("ROADWY", "Road"),
    117: ("RUNWAY", "Runway"),
    118: ("SNDWAV", "Sand waves"),
    119: ("SEAARE", "Sea area / named water area"),
    120: ("SPLARE", "Sea-plane landing area"),
    121: ("SBDARE", "Seabed area"),
    122: ("SLCONS", "Shoreline Construction"),
    123: ("SISTAT", "Signal station, traffic"),
    124: ("SISTAW", "Signal station, warning"),
    125: ("SILTNK", "Silo / tank"),
    126: ("SLOTOP", "Slope topline"),
    127: ("SLOGRD", "Sloping ground"),
    128: ("SMCFAC", "Small craft facility"),
    129: ("SOUNDG", "Sounding"),
    130: ("SPRING", "Spring"),
    131: ("SQUARE", "Square"),
    132: ("STSLNE", "Straight territorial sea baseline"),
    133: ("SUBTLN", "Submarine transit lane"),
    134: ("SWPARE", "Swept Area"),
    135: ("TESARE", "Territorial sea area"),
    136: ("TS_PRH", "Tidal stream - harmonic prediction"),
    137: ("TS_PNH", "Tidal stream - non-harmonic prediction"),
    138: ("TS_PAD", "Tidal stream panel data"),
    139: ("TS_TIS", "Tidal stream - time series"),
    140: ("T_HMON", "Tide - harmonic prediction"),
    141: ("T_NHMN", "Tide - non-harmonic prediction"),
    142: ("T_TIMS", "Tidal stream - time series"),
    143: ("TIDEWY", "Tideway"),
    144: ("TOPMAR", "Top mark"),
    145: ("TSELNE", "Traffic Separation Line"),
    146: ("TSSBND", "Traffic Separation Scheme  Boundary"),
    147: ("TSSCRS", "Traffic Separation Scheme Crossing"),
    148: ("TSSLPT", "Traffic Separation Scheme  Lane part"),
    149: ("TSSRON", "Traffic Separation Scheme  Roundabout"),
    150: ("TSEZNE", "Traffic Separation Zone"),
    151: ("TUNNEL", "Tunnel"),
    152: ("TWRTPT", "Two-way route  part"),
    153: ("UWTROC", "Underwater rock / awash rock"),
    154: ("UNSARE", "Unsurveyed area"),
    155: ("VEGATN", "Vegetation"),
    156: ("WATTUR", "Water turbulence"),
    157: ("WATFAL", "Waterfall"),
    158: ("WEDKLP", "Weed/Kelp"),
    159: ("WRECKS", "Wreck"),
    160: ("TS_FEB", "Tidal stream - flood/ebb"),
    161: ("ARCSLN", "Archipelagic Sea Lane"),
    162: ("ASLXIS", "Archipelagic Sea Lane Axis"),
    163: ("NEWOBJ", "New Object"),
    300: ("M_ACCY", "Accuracy of data"),
    301: ("M_CSCL", "Compilation scale of data"),
    302: ("M_COVR", "Coverage"),
    303: ("M_HDAT", "Horizontal datum of data"),
    304: ("M_HOPA", "Horizontal datum shift parameters"),
    305: ("M_NPUB", "Nautical publication information"),
    306: ("M_NSYS", "Navigational system of marks"),
    307: ("M_PROD", "Production information"),
    308: ("M_QUAL", "Quality of data"),
    309: ("M_SDAT", "Sounding datum"),
    310: ("M_SREL", "Survey reliability"),
    311: ("M_UNIT", "Units of measurement of data"),
    312: ("M_VDAT", "Vertical datum of data"),
    313: ("m_pyup", "Pydro update data"),
    400: ("C_AGGR", "Aggregation"),
    401: ("C_ASSO", "Association"),
    402: ("C_STAC", "Stacked on/stacked under"),
    500: ("$AREAS", "Cartographic area"),
    501: ("$LINES", "Cartographic line"),
    502: ("$CSYMB", "Cartographic symbol"),
    503: ("$COMPS", "Compass"),
    504: ("$TEXTS", "Text"),
    644: ("cvrage", "Coverage Area"),
    696: ("brklne", "Breakline"),
    11001: ("usrmrk", "User marker"),
    11003: ("survey", "Survey project"),
    11004: ("surfac", "Bathymetric surface"),
    11008: ("prodpf", "Product Profile"),
}
ob_attribs = {
    "AGENCY": (1, "Agency responsible for production"),
    "BCNSHP": (2, "Beacon shape"),
    "BUISHP": (3, "Building shape"),
    "BOYSHP": (4, "Buoy shape"),
    "BURDEP": (5, "Buried depth"),
    "CALSGN": (6, "Call sign"),
    "CATAIR": (7, "Category of airport/airfield"),
    "CATACH": (8, "Category of anchorage"),
    "CATBRG": (9, "Category of bridge"),
    "CATBUA": (10, "Category of built-up area"),
    "CATCBL": (11, "Category of cable"),
    "CATCAN": (12, "Category of canal"),
    "CATCAM": (13, "Category of cardinal mark"),
    "CATCHP": (14, "Category of checkpoint"),
    "CATCOA": (15, "Category of coastline"),
    "CATCTR": (16, "Category of control point"),
    "CATCON": (17, "Category of conveyor"),
    "CATCOV": (18, "Category of coverage"),
    "CATCRN": (19, "Category of crane"),
    "CATDAM": (20, "Category of dam"),
    "CATDIS": (21, "Category of distance mark"),
    "CATDOC": (22, "Category of dock"),
    "CATDPG": (23, "Category of dumping ground"),
    "CATFNC": (24, "Category of  fence/wall"),
    "CATFRY": (25, "Category of ferry"),
    "CATFIF": (26, "Category of  fishing  facility"),
    "CATFOG": (27, "Category of  fog signal"),
    "CATFOR": (28, "Category of  fortified structure"),
    "CATGAT": (29, "Category of gate"),
    "CATHAF": (30, "Category of harbour facility"),
    "CATHLK": (31, "Category of hulk"),
    "CATICE": (32, "Category of  ice"),
    "CATINB": (33, "Category of installation buoy"),
    "CATLND": (34, "Category of land region"),
    "CATLMK": (35, "Category of landmark"),
    "CATLAM": (36, "Category of lateral mark"),
    "CATLIT": (37, "Category of light"),
    "CATMFA": (38, "Category of marine farm/culture"),
    "CATMPA": (39, "Category of military practice area"),
    "CATMOR": (40, "Category of mooring/warping facility"),
    "CATNAV": (41, "Category of navigation line"),
    "CATOBS": (42, "Category of obstruction"),
    "CATOFP": (43, "Category of offshore platform"),
    "CATOLB": (44, "Category of oil barrier"),
    "CATPLE": (45, "Category of pile"),
    "CATPIL": (46, "Category of pilot boarding place"),
    "CATPIP": (47, "Category of pipeline / pipe"),
    "CATPRA": (48, "Category of production area"),
    "CATPYL": (49, "Category of pylon"),
    "CATQUA": (50, "Category of quality of data"),
    "CATRAS": (51, "Category of radar station"),
    "CATRTB": (52, "Category of radar transponder beacon"),
    "CATROS": (53, "Category of radio station"),
    "CATTRK": (54, "Category of recommended track"),
    "CATRSC": (55, "Category of rescue station"),
    "CATREA": (56, "Category of restricted area"),
    "CATROD": (57, "Category of road"),
    "CATRUN": (58, "Category of runway"),
    "CATSEA": (59, "Category of sea area"),
    "CATSLC": (60, "Category of shoreline construction"),
    "CATSIT": (61, "Category of signal station, traffic"),
    "CATSIW": (62, "Category of signal station, warning"),
    "CATSIL": (63, "Category of silo/tank"),
    "CATSLO": (64, "Category of slope"),
    "CATSCF": (65, "Category of small craft facility"),
    "CATSPM": (66, "Category of special purpose mark"),
    "CATTSS": (67, "Category of Traffic Separation Scheme"),
    "CATVEG": (68, "Category of vegetation"),
    "CATWAT": (69, "Category of water turbulence"),
    "CATWED": (70, "Category of weed/kelp"),
    "CATWRK": (71, "Category of wreck"),
    "CATZOC": (72, "Category of zone of confidence data"),
    "$SPACE": (73, "Character spacing"),
    "$CHARS": (74, "Character specification"),
    "COLOUR": (75, "Colour"),
    "COLPAT": (76, "Colour pattern"),
    "COMCHA": (77, "Communication channel"),
    "$CSIZE": (78, "Compass size"),
    "CPDATE": (79, "Compilation date"),
    "CSCALE": (80, "Compilation scale"),
    "CONDTN": (81, "Condition"),
    "CONRAD": (82, "Conspicuous, Radar"),
    "CONVIS": (83, "Conspicuous, visual"),
    "CURVEL": (84, "Current velocity"),
    "DATEND": (85, "Date end"),
    "DATSTA": (86, "Date start"),
    "DRVAL1": (87, "Depth range value 1"),
    "DRVAL2": (88, "Depth range value 2"),
    "DUNITS": (89, "Depth units"),
    "ELEVAT": (90, "Elevation"),
    "ESTRNG": (91, "Estimated range of transmission"),
    "EXCLIT": (92, "Exhibition condition of light"),
    "EXPSOU": (93, "Exposition of sounding"),
    "FUNCTN": (94, "Function"),
    "HEIGHT": (95, "Height"),
    "HUNITS": (96, "Height/length units"),
    "HORACC": (97, "Horizontal accuracy"),
    "HORCLR": (98, "Horizontal clearance"),
    "HORLEN": (99, "Horizontal length"),
    "HORWID": (100, "Horizontal width"),
    "ICEFAC": (101, "Ice factor"),
    "INFORM": (102, "Information"),
    "JRSDTN": (103, "Jurisdiction"),
    "$JUSTH": (104, "Justification - horizontal"),
    "$JUSTV": (105, "Justification - vertical"),
    "LIFCAP": (106, "Lifting capacity"),
    "LITCHR": (107, "Light characteristic"),
    "LITVIS": (108, "Light visibility"),
    "MARSYS": (109, "Marks navigational - System of"),
    "MLTYLT": (110, "Multiplicity of lights"),
    "NATION": (111, "Nationality"),
    "NATCON": (112, "Nature of construction"),
    "NATSUR": (113, "Nature of surface"),
    "NATQUA": (114, "Nature of surface - qualifying terms"),
    "NMDATE": (115, "Notice to Mariners date"),
    "OBJNAM": (116, "Object name"),
    "ORIENT": (117, "Orientation"),
    "PEREND": (118, "Periodic date end"),
    "PERSTA": (119, "Periodic date start"),
    "PICREP": (120, "Pictorial representation"),
    "PILDST": (121, "Pilot district"),
    "PRCTRY": (122, "Producing country"),
    "PRODCT": (123, "Product"),
    "PUBREF": (124, "Publication reference"),
    "QUASOU": (125, "Quality of sounding measurement"),
    "RADWAL": (126, "Radar wave length"),
    "RADIUS": (127, "Radius"),
    "RECDAT": (128, "Recording date"),
    "RECIND": (129, "Recording indication"),
    "RYRMGV": (130, "Reference year for magnetic variation"),
    "RESTRN": (131, "Restriction"),
    "SCAMAX": (132, "Scale maximum"),
    "SCAMIN": (133, "Scale minimum"),
    "SCVAL1": (134, "Scale value one"),
    "SCVAL2": (135, "Scale value two"),
    "SECTR1": (136, "Sector limit one"),
    "SECTR2": (137, "Sector limit two"),
    "SHIPAM": (138, "Shift parameters"),
    "SIGFRQ": (139, "Signal frequency"),
    "SIGGEN": (140, "Signal generation"),
    "SIGGRP": (141, "Signal group"),
    "SIGPER": (142, "Signal period"),
    "SIGSEQ": (143, "Signal sequence"),
    "SOUACC": (144, "Sounding accuracy"),
    "SDISMX": (145, "Sounding distance - maximum"),
    "SDISMN": (146, "Sounding distance - minimum"),
    "SORDAT": (147, "Source date"),
    "SORIND": (148, "Source indication"),
    "STATUS": (149, "Status"),
    "SURATH": (150, "Survey authority"),
    "SUREND": (151, "Survey date - end"),
    "SURSTA": (152, "Survey date - start"),
    "SURTYP": (153, "Survey type"),
    "$SCALE": (154, "Symbol scaling factor"),
    "$SCODE": (155, "Symbolization code"),
    "TECSOU": (156, "Technique of sounding measurement"),
    "$TXSTR": (157, "Text string"),
    "TXTDSC": (158, "Textual description"),
    "TS_TSP": (159, "Tidal stream - panel values"),
    "TS_TSV": (160, "Tidal stream, current - time series values"),
    "T_ACWL": (161, "Tide - accuracy of water level"),
    "T_HWLW": (162, "Tide - high and low water values"),
    "T_MTOD": (163, "Tide - method of tidal prediction"),
    "T_THDF": (164, "Tide - time and height differences"),
    "T_TINT": (165, "Tide, current - time interval of values"),
    "T_TSVL": (166, "Tide - time series values"),
    "T_VAHC": (167, "Tide - value of harmonic constituents"),
    "TIMEND": (168, "Time end"),
    "TIMSTA": (169, "Time start"),
    "$TINTS": (170, "Tint"),
    "TOPSHP": (171, "Topmark/daymark shape"),
    "TRAFIC": (172, "Traffic flow"),
    "VALACM": (173, "Value of annual change in magnetic variation"),
    "VALDCO": (174, "Value of depth contour"),
    "VALLMA": (175, "Value of local magnetic anomaly"),
    "VALMAG": (176, "Value of magnetic variation"),
    "VALMXR": (177, "Value of maximum range"),
    "VALNMR": (178, "Value of nominal range"),
    "VALSOU": (179, "Value of sounding"),
    "VERACC": (180, "Vertical accuracy"),
    "VERCLR": (181, "Vertical clearance"),
    "VERCCL": (182, "Vertical clearance, closed"),
    "VERCOP": (183, "Vertical clearance, open"),
    "VERCSA": (184, "Vertical clearance, safe"),
    "VERDAT": (185, "Vertical datum"),
    "VERLEN": (186, "Vertical length"),
    "WATLEV": (187, "Water level effect"),
    "CAT_TS": (188, "Category of Tidal stream"),
    "PUNITS": (189, "Positional accuracy units"),
    "CLSDEF": (190, "Defining characteristics of a new object"),
    "CLSNAM": (191, "Descriptive name of a new object"),
    "SYMINS": (192, "S-52 symbol instruction"),
    "NINFOM": (300, "Information in national language"),
    "NOBJNM": (301, "Object name in national language"),
    "NPLDST": (302, "Pilot district in national language"),
    "$NTXST": (303, "Text string in national language"),
    "NTXTDS": (304, "Textual description in national language"),
    "HORDAT": (400, "Horizontal datum"),
    "POSACC": (401, "Positional Accuracy"),
    "QUAPOS": (402, "Quality of position"),
    "cvgtyp": (1039, "Coverage Object Type"),
    "dbkyid": (1041, "Database Key ID (Pydro XML Event digest)"),
    "srfres": (1073, "Grid surface resolution"),
    "modtim": (1115, "Last modified time"),
    "mk_pic": (1116, "Marker picture file"),
    "userid": (1117, "Unique ID (Pydro XML DispName)"),
    "remrks": (1118, "Remarks (Pydro XML)"),
    "recomd": (1119, "Recommendations (Pydro XML)"),
    "updtim": (1220, "Update Time (Pydro XML Event data)"),
    "mk_doc": (1221, "External Text Reference"),
    "mk_edi": (1297, "Marker edit"),
    "areout": (1298, "Outline for area object"),
    "obstim": (1305, "Observed time"),
    "obsdpt": (1306, "Observed depth"),
    "tidadj": (1307, "Tidal adjustment"),
    "tidfil": (1308, "Tide Correction File"),
    "descrp": (2000, "Description of cartographic action"),
    "asgnmt": (2001, "Assignment flag"),
    "prmsec": (2002, "Primary/Secondary status"),
    "images": (2003, "Image(s)"),
    "onotes": (2004, "Office notes"),
    "sftype": (2005, "Special feature type"),
    "keywrd": (2006, "Keyword"),
    "acqsts": (2007, "Acquisition status"),
    "cnthgt": (2008, "Contact height"),
    "invreq": (2009, "Investigation requirements"),
    "prkyid": (2010, "Primary feature dbkyid"),
    "hsdrec": (2011, "HSD Charting Recommendation"),
    "mk_tim": (10014, "Marker timestamp"),
    "mk_txt": (10015, "Marker text"),
    "mk_sta": (10016, "Marker status"),
    "mk_unm": (10017, "Marker user name"),
    "mk_rel": (10018, "Related feature ids"),
    "subnam": (10020, "Object subtitle name"),
    "surhir": (10022, "Hydrographic Instruction reference ID"),
    "srfcat": (10024, "Category of bathymetric surface"),
    "idprnt": (10026, "Unique identifier of parent object"),
    "cntdir": (18687, "Contour Slope"),
    "cretim": (18688, "Creation time"),
    "srftyp": (18689, "Storage Type"),
    "objst8": (18690, "Object State"),
    "uidcre": (18691, "User id of the object's creator"),
}
attribs_codes = {
    1: ("AGENCY", "Agency responsible for production"),
    2: ("BCNSHP", "Beacon shape"),
    3: ("BUISHP", "Building shape"),
    4: ("BOYSHP", "Buoy shape"),
    5: ("BURDEP", "Buried depth"),
    6: ("CALSGN", "Call sign"),
    7: ("CATAIR", "Category of airport/airfield"),
    8: ("CATACH", "Category of anchorage"),
    9: ("CATBRG", "Category of bridge"),
    10: ("CATBUA", "Category of built-up area"),
    11: ("CATCBL", "Category of cable"),
    12: ("CATCAN", "Category of canal"),
    13: ("CATCAM", "Category of cardinal mark"),
    14: ("CATCHP", "Category of checkpoint"),
    15: ("CATCOA", "Category of coastline"),
    16: ("CATCTR", "Category of control point"),
    17: ("CATCON", "Category of conveyor"),
    18: ("CATCOV", "Category of coverage"),
    19: ("CATCRN", "Category of crane"),
    20: ("CATDAM", "Category of dam"),
    21: ("CATDIS", "Category of distance mark"),
    22: ("CATDOC", "Category of dock"),
    23: ("CATDPG", "Category of dumping ground"),
    24: ("CATFNC", "Category of  fence/wall"),
    25: ("CATFRY", "Category of ferry"),
    26: ("CATFIF", "Category of  fishing  facility"),
    27: ("CATFOG", "Category of  fog signal"),
    28: ("CATFOR", "Category of  fortified structure"),
    29: ("CATGAT", "Category of gate"),
    30: ("CATHAF", "Category of harbour facility"),
    31: ("CATHLK", "Category of hulk"),
    32: ("CATICE", "Category of  ice"),
    33: ("CATINB", "Category of installation buoy"),
    34: ("CATLND", "Category of land region"),
    35: ("CATLMK", "Category of landmark"),
    36: ("CATLAM", "Category of lateral mark"),
    37: ("CATLIT", "Category of light"),
    38: ("CATMFA", "Category of marine farm/culture"),
    39: ("CATMPA", "Category of military practice area"),
    40: ("CATMOR", "Category of mooring/warping facility"),
    41: ("CATNAV", "Category of navigation line"),
    42: ("CATOBS", "Category of obstruction"),
    43: ("CATOFP", "Category of offshore platform"),
    44: ("CATOLB", "Category of oil barrier"),
    45: ("CATPLE", "Category of pile"),
    46: ("CATPIL", "Category of pilot boarding place"),
    47: ("CATPIP", "Category of pipeline / pipe"),
    48: ("CATPRA", "Category of production area"),
    49: ("CATPYL", "Category of pylon"),
    50: ("CATQUA", "Category of quality of data"),
    51: ("CATRAS", "Category of radar station"),
    52: ("CATRTB", "Category of radar transponder beacon"),
    53: ("CATROS", "Category of radio station"),
    54: ("CATTRK", "Category of recommended track"),
    55: ("CATRSC", "Category of rescue station"),
    56: ("CATREA", "Category of restricted area"),
    57: ("CATROD", "Category of road"),
    58: ("CATRUN", "Category of runway"),
    59: ("CATSEA", "Category of sea area"),
    60: ("CATSLC", "Category of shoreline construction"),
    61: ("CATSIT", "Category of signal station, traffic"),
    62: ("CATSIW", "Category of signal station, warning"),
    63: ("CATSIL", "Category of silo/tank"),
    64: ("CATSLO", "Category of slope"),
    65: ("CATSCF", "Category of small craft facility"),
    66: ("CATSPM", "Category of special purpose mark"),
    67: ("CATTSS", "Category of Traffic Separation Scheme"),
    68: ("CATVEG", "Category of vegetation"),
    69: ("CATWAT", "Category of water turbulence"),
    70: ("CATWED", "Category of weed/kelp"),
    71: ("CATWRK", "Category of wreck"),
    72: ("CATZOC", "Category of zone of confidence data"),
    73: ("$SPACE", "Character spacing"),
    74: ("$CHARS", "Character specification"),
    75: ("COLOUR", "Colour"),
    76: ("COLPAT", "Colour pattern"),
    77: ("COMCHA", "Communication channel"),
    78: ("$CSIZE", "Compass size"),
    79: ("CPDATE", "Compilation date"),
    80: ("CSCALE", "Compilation scale"),
    81: ("CONDTN", "Condition"),
    82: ("CONRAD", "Conspicuous, Radar"),
    83: ("CONVIS", "Conspicuous, visual"),
    84: ("CURVEL", "Current velocity"),
    85: ("DATEND", "Date end"),
    86: ("DATSTA", "Date start"),
    87: ("DRVAL1", "Depth range value 1"),
    88: ("DRVAL2", "Depth range value 2"),
    89: ("DUNITS", "Depth units"),
    90: ("ELEVAT", "Elevation"),
    91: ("ESTRNG", "Estimated range of transmission"),
    92: ("EXCLIT", "Exhibition condition of light"),
    93: ("EXPSOU", "Exposition of sounding"),
    94: ("FUNCTN", "Function"),
    95: ("HEIGHT", "Height"),
    96: ("HUNITS", "Height/length units"),
    97: ("HORACC", "Horizontal accuracy"),
    98: ("HORCLR", "Horizontal clearance"),
    99: ("HORLEN", "Horizontal length"),
    100: ("HORWID", "Horizontal width"),
    101: ("ICEFAC", "Ice factor"),
    102: ("INFORM", "Information"),
    103: ("JRSDTN", "Jurisdiction"),
    104: ("$JUSTH", "Justification - horizontal"),
    105: ("$JUSTV", "Justification - vertical"),
    106: ("LIFCAP", "Lifting capacity"),
    107: ("LITCHR", "Light characteristic"),
    108: ("LITVIS", "Light visibility"),
    109: ("MARSYS", "Marks navigational - System of"),
    110: ("MLTYLT", "Multiplicity of lights"),
    111: ("NATION", "Nationality"),
    112: ("NATCON", "Nature of construction"),
    113: ("NATSUR", "Nature of surface"),
    114: ("NATQUA", "Nature of surface - qualifying terms"),
    115: ("NMDATE", "Notice to Mariners date"),
    116: ("OBJNAM", "Object name"),
    117: ("ORIENT", "Orientation"),
    118: ("PEREND", "Periodic date end"),
    119: ("PERSTA", "Periodic date start"),
    120: ("PICREP", "Pictorial representation"),
    121: ("PILDST", "Pilot district"),
    122: ("PRCTRY", "Producing country"),
    123: ("PRODCT", "Product"),
    124: ("PUBREF", "Publication reference"),
    125: ("QUASOU", "Quality of sounding measurement"),
    126: ("RADWAL", "Radar wave length"),
    127: ("RADIUS", "Radius"),
    128: ("RECDAT", "Recording date"),
    129: ("RECIND", "Recording indication"),
    130: ("RYRMGV", "Reference year for magnetic variation"),
    131: ("RESTRN", "Restriction"),
    132: ("SCAMAX", "Scale maximum"),
    133: ("SCAMIN", "Scale minimum"),
    134: ("SCVAL1", "Scale value one"),
    135: ("SCVAL2", "Scale value two"),
    136: ("SECTR1", "Sector limit one"),
    137: ("SECTR2", "Sector limit two"),
    138: ("SHIPAM", "Shift parameters"),
    139: ("SIGFRQ", "Signal frequency"),
    140: ("SIGGEN", "Signal generation"),
    141: ("SIGGRP", "Signal group"),
    142: ("SIGPER", "Signal period"),
    143: ("SIGSEQ", "Signal sequence"),
    144: ("SOUACC", "Sounding accuracy"),
    145: ("SDISMX", "Sounding distance - maximum"),
    146: ("SDISMN", "Sounding distance - minimum"),
    147: ("SORDAT", "Source date"),
    148: ("SORIND", "Source indication"),
    149: ("STATUS", "Status"),
    150: ("SURATH", "Survey authority"),
    151: ("SUREND", "Survey date - end"),
    152: ("SURSTA", "Survey date - start"),
    153: ("SURTYP", "Survey type"),
    154: ("$SCALE", "Symbol scaling factor"),
    155: ("$SCODE", "Symbolization code"),
    156: ("TECSOU", "Technique of sounding measurement"),
    157: ("$TXSTR", "Text string"),
    158: ("TXTDSC", "Textual description"),
    159: ("TS_TSP", "Tidal stream - panel values"),
    160: ("TS_TSV", "Tidal stream, current - time series values"),
    161: ("T_ACWL", "Tide - accuracy of water level"),
    162: ("T_HWLW", "Tide - high and low water values"),
    163: ("T_MTOD", "Tide - method of tidal prediction"),
    164: ("T_THDF", "Tide - time and height differences"),
    165: ("T_TINT", "Tide, current - time interval of values"),
    166: ("T_TSVL", "Tide - time series values"),
    167: ("T_VAHC", "Tide - value of harmonic constituents"),
    168: ("TIMEND", "Time end"),
    169: ("TIMSTA", "Time start"),
    170: ("$TINTS", "Tint"),
    171: ("TOPSHP", "Topmark/daymark shape"),
    172: ("TRAFIC", "Traffic flow"),
    173: ("VALACM", "Value of annual change in magnetic variation"),
    174: ("VALDCO", "Value of depth contour"),
    175: ("VALLMA", "Value of local magnetic anomaly"),
    176: ("VALMAG", "Value of magnetic variation"),
    177: ("VALMXR", "Value of maximum range"),
    178: ("VALNMR", "Value of nominal range"),
    179: ("VALSOU", "Value of sounding"),
    180: ("VERACC", "Vertical accuracy"),
    181: ("VERCLR", "Vertical clearance"),
    182: ("VERCCL", "Vertical clearance, closed"),
    183: ("VERCOP", "Vertical clearance, open"),
    184: ("VERCSA", "Vertical clearance, safe"),
    185: ("VERDAT", "Vertical datum"),
    186: ("VERLEN", "Vertical length"),
    187: ("WATLEV", "Water level effect"),
    188: ("CAT_TS", "Category of Tidal stream"),
    189: ("PUNITS", "Positional accuracy units"),
    190: ("CLSDEF", "Defining characteristics of a new object"),
    191: ("CLSNAM", "Descriptive name of a new object"),
    192: ("SYMINS", "S-52 symbol instruction"),
    300: ("NINFOM", "Information in national language"),
    301: ("NOBJNM", "Object name in national language"),
    302: ("NPLDST", "Pilot district in national language"),
    303: ("$NTXST", "Text string in national language"),
    304: ("NTXTDS", "Textual description in national language"),
    400: ("HORDAT", "Horizontal datum"),
    401: ("POSACC", "Positional Accuracy"),
    402: ("QUAPOS", "Quality of position"),
    1039: ("cvgtyp", "Coverage Object Type"),
    1041: ("dbkyid", "Database Key ID (Pydro XML Event digest)"),
    1073: ("srfres", "Grid surface resolution"),
    1115: ("modtim", "Last modified time"),
    1116: ("mk_pic", "Marker picture file"),
    1117: ("userid", "Unique ID (Pydro XML DispName)"),
    1118: ("remrks", "Remarks (Pydro XML)"),
    1119: ("recomd", "Recommendations (Pydro XML)"),
    1220: ("updtim", "Update Time (Pydro XML Event data)"),
    1221: ("mk_doc", "External Text Reference"),
    1297: ("mk_edi", "Marker edit"),
    1298: ("areout", "Outline for area object"),
    1305: ("obstim", "Observed time"),
    1306: ("obsdpt", "Observed depth"),
    1307: ("tidadj", "Tidal adjustment"),
    1308: ("tidfil", "Tide Correction File"),
    2000: ("descrp", "Description of cartographic action"),
    2001: ("asgnmt", "Assignment flag"),
    2002: ("prmsec", "Primary/Secondary status"),
    2003: ("images", "Image(s)"),
    2004: ("onotes", "Office notes"),
    2005: ("sftype", "Special feature type"),
    2006: ("keywrd", "Keyword"),
    2007: ("acqsts", "Acquisition status"),
    2008: ("cnthgt", "Contact height"),
    2009: ("invreq", "Investigation requirements"),
    2010: ("prkyid", "Primary feature dbkyid"),
    2011: ("hsdrec", "HSD Charting Recommendation"),
    10014: ("mk_tim", "Marker timestamp"),
    10015: ("mk_txt", "Marker text"),
    10016: ("mk_sta", "Marker status"),
    10017: ("mk_unm", "Marker user name"),
    10018: ("mk_rel", "Related feature ids"),
    10020: ("subnam", "Object subtitle name"),
    10022: ("surhir", "Hydrographic Instruction reference ID"),
    10024: ("srfcat", "Category of bathymetric surface"),
    10026: ("idprnt", "Unique identifier of parent object"),
    18687: ("cntdir", "Contour Slope"),
    18688: ("cretim", "Creation time"),
    18689: ("srftyp", "Storage Type"),
    18690: ("objst8", "Object State"),
    18691: ("uidcre", "User id of the object's creator"),
}
structure_objects = (
    5,
    6,
    7,
    8,
    9,
    14,
    15,
    16,
    17,
    18,
    19,
    11,
    12,
    39,
    76,
    77,
    74,
    84,
    87,
    90,
    122,
)
equipment_objects = (39, 58, 75, 102, 105, 113, 103, 123, 124, 144)
for k, v in ob_classes.items():
    try:
        exec("%s=%d" % (k, v[0]))
    except:
        pass
for k, v in ob_attribs.items():
    try:
        exec("%s=%d" % (k, v[0]))
    except:
        pass
