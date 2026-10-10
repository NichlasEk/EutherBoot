/* Disposable initramfs PID 1. No disks, network or firmware variables are written. */
#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <sys/mount.h>
#include <sys/reboot.h>
#include <sys/utsname.h>

int main(void) {
    char cmdline[4096] = {0};
    struct utsname info;
    setbuf(stdout, NULL);
    if (getpid() != 1) return 1; /* Refuse accidental host execution. */
    if (mount("proc", "/proc", "proc", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL)) goto fail;
    FILE *file = fopen("/proc/cmdline", "r");
    if (!file) goto fail;
    if (!fgets(cmdline, sizeof(cmdline), file)) { fclose(file); goto fail; }
    fclose(file);
    if (uname(&info)) goto fail;
    printf("EUTHERBOOT_LINUX_UNAME %s\n", info.release);
    printf("EUTHERBOOT_LINUX_CMDLINE %s", cmdline);
    if (!strstr(cmdline, "eutherboot_probe=owner-controlled")) goto fail;
    if (strstr(cmdline, "eutherboot_mode=stub")) puts("EUTHERBOOT_LINUX_PID1_OK stub");
    else if (strstr(cmdline, "eutherboot_mode=uki")) puts("EUTHERBOOT_LINUX_PID1_OK uki");
    else goto fail;
    reboot(RB_POWER_OFF);
    for (;;) pause();
fail:
    puts("EUTHERBOOT_LINUX_PROBE_FAILED");
    reboot(RB_POWER_OFF);
    for (;;) pause();
}
