#include <windows.h>

#if BUILDING_DLL
#define DLLIMPORT __declspec(dllexport)
#else
#define DLLIMPORT __declspec(dllimport)
#endif

//Compile with
//i686-w64-mingw32-gcc -shared -o PoCmsgbox.dll TEMPLATE8-PoCmsgboxdll.c
//
//Code will execute when the DLL is attached 
//On target system execute with
//rundll32.exe PoCmsgbox.dll,any
//rundll32.exe PoCmsgbox.dll,EntryPoint

BOOL WINAPI DllMain(HINSTANCE hinstDLL, DWORD fdwReason, LPVOID lpvReserved)
{
	switch (fdwReason)
	{
	case DLL_PROCESS_ATTACH:
	{
		codehere();
		break;
	}
	case DLL_PROCESS_DETACH:
	{
		break;
	}
	case DLL_THREAD_ATTACH:
	{
		break;
	}
	case DLL_THREAD_DETACH:
	{
		break;
	}
	}
	return TRUE;
}


int codehere(){

	MessageBox(0, "Hello World from DLL !!\n", "Dll Injection PoC", MB_ICONINFORMATION);
	//WinExec("cmd.exe /k C:\\windows\\system32\\cmd.exe", 0);
	//
}

//export EntryPoint
int EntryPoint(){
	MessageBox(0, "EntryPoint function found!!! :) \n", "EntryPoint", MB_ICONINFORMATION);

}
