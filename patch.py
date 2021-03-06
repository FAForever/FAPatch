import sys
import os
from subprocess import check_output as proc_call, CalledProcessError
import shutil

def pwrite(fd, data, offset):
	pos = os.lseek(fd, 0, os.SEEK_CUR)
	os.lseek(fd, offset, os.SEEK_SET)
	assert os.write(fd, data) == len(data)
	os.lseek(fd, pos, os.SEEK_SET)

if sys.version_info[0] != 3:
	print("Python 2 is not supported")
	os.exit(1)

from argparse import ArgumentParser

def call(command):
	try:
		output = proc_call(command)
	except CalledProcessError as e:
		output = e.output
	if output:
		print('Executing','"%s":' % ' '.join(command))
		for line in output.splitlines():
			print(' ',line.decode())

def silly_hand_coded_sector_patch(file):
	fd = file.fileno()
	patch = { 0x136 : '07',
			  0x181 : 'C5',
			  0x188 : 'AC 24',
			  0x1B9 : 'F0 E3 00 EC B8 04 00',
			  0x1C8 : '00 00 00 00 00 00 00 00',
			  0x318 : '2E 65 78 74 00 00 00 00 '
	                  '00 15 00 00 00 B0 E8 00 00 15 00 00 00 D0 BD 00 '
	                  '00 00 00 00 00 00 00 00 00 00 00 00 20 00 00 60'}

	for pos, diff in patch.items():
		pwrite(fd, bytes.fromhex(diff), pos)

def parseCommandLine():
	parser = ArgumentParser(description='Forged Alliance Patcher')
	parser.add_argument('-c','--c-code', action='store_true', help='Compile the c patch version instead.')
	parser.add_argument('output_file', nargs='?', help='Optional filename to place the patched version at.')
	return parser.parse_args()

def nasm_compile(filename, filename_out = None):
	assert filename.endswith('.s')
	print("Compiling %s" % filename)

	if filename_out is None:
		filename_out = 'build/'+filename[:-2]+'.asm.bin'
	# Compile ext_sector.s
	call(['nasm', filename,'-o', filename_out])
	return open(filename_out,'rb').read()

def apply_hook(pe, filename):
	hookf = open(filename, 'rb')
	head = hookf.readline().split()
	if head[1] != b'HOOK':
		raise Exception("apply_hook with a non-hook file: "+filename)

	print("Applying hook '"+head[2].decode()+"'")

	if head[3] != b'ROffset':
		raise Exception("No hook offset")
	raw_off = int(head[5], 0)
	hookf.close()

	code = nasm_compile(filename)

	print("Applying at 0x%08x: %s" % (raw_off, code))
	pe.seek(raw_off)
	pe.write(code)

def main():

	args = parseCommandLine()

	print("Patching ForgedAlliance_base.exe to ForgedAlliance_ext.exe")

	shutil.copyfile('ForgedAlliance_base.exe', 'ForgedAlliance_ext.exe')
	# Patch the binary
	filename = 'ForgedAlliance_ext.exe'

	pe = open(filename,'r+b')

	print('Patching in a .ext sector')
	silly_hand_coded_sector_patch(pe)
	
	if not os.path.exists('build/'):
		os.makedirs('build/')

	hooks = ['hook_LoadSavedGame.s',
			 'hook_ArmyGetHandicap.s',
			 'hook_Walls.s' ]
			 #,
			 #'hook_ValidateFocusArmyRequest.s']

	for hook in hooks:
		apply_hook(pe, hook)

	verisign_offset = 0xBDD000
	verisign_size = 0x1500

	pe.seek(verisign_offset)
	pe.write( bytes([0]*verisign_size) )

	ext_section_offset = 0xBDD000
	ext_section_filename = 'ext_sector.s'

	pe.seek(ext_section_offset)
	if args.c_code:
		call(['python','build_ext.py'])
		with open('build/ext_sector.bin','rb') as f:
			size = os.fstat(f.fileno()).st_size
			if size > 0x1500:
				raise RuntimeError('C compiled sector size too big.')
			else:
				pe.write( f.read() )
	else:
		pe.write( nasm_compile(ext_section_filename) )

	pe.close()
	print("Done.")
	if args.output_file:
		shutil.move(filename, args.output_file)
		print("Moved",filename,"to",args.output_file)

if __name__ == "__main__":
	main()

	
