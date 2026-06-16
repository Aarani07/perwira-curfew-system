let videoStream = null;
let mode = "face";
let detecting = false;
let currentFacingMode = "user"; // front camera
let qrRefreshTimer = null;
let qrCountdownTimer = null;
const QR_WINDOW_SECONDS = 180;

/* ================= CONFIG ================= */
function getUserRole() {
    return window.userRole || "student";
}

function isStudent() {
    return getUserRole() === "student";
}

function getDetectionEndpoint() {
    return mode === "face"
        ? "/security/verify-face"
        : "/security/verify-qr";
}

/* ================= STUDENT QR ================= */
async function openStudentQR() {
    document.body.classList.add("camera-open");

    const modal = document.getElementById("globalCameraModal");
    if (!modal) {
        alert("QR modal not found.");
        return;
    }

    modal.style.display = "flex";
    modal.style.visibility = "visible";
    modal.style.opacity = "1";

    await loadStudentRotatingQR();
    startStudentQrAutoRefresh();
}

async function loadStudentRotatingQR() {
    try {
        const response = await fetch("/student/get-rotating-qr", {
            method: "GET",
            credentials: "same-origin"
        });

        const result = await response.json();

        if (!result.success) {
            showStudentQrError(result.message || "Unable to load QR code.");
            return;
        }

        const qrImage = document.getElementById("studentQrImage");
        const qrName = document.getElementById("studentQrName");
        const qrMatric = document.getElementById("studentQrMatric");
        const qrBlock = document.getElementById("studentQrBlock");
        const qrRoom = document.getElementById("studentQrRoom");

        if (qrImage) qrImage.src = result.qr_image || "";
        if (qrName) qrName.innerText = result.student_name || "-";
        if (qrMatric) qrMatric.innerText = result.matric_no || "-";
        if (qrBlock) qrBlock.innerText = result.block || "-";
        if (qrRoom) qrRoom.innerText = result.room_no || "-";

        startStudentQrCountdown(result.expires_in || QR_WINDOW_SECONDS);
    } catch (error) {
        console.error("Error loading student QR:", error);
        showStudentQrError("Failed to load QR code.");
    }
}

function startStudentQrCountdown(expiresIn) {
    clearInterval(qrCountdownTimer);

    let remaining = expiresIn;
    updateStudentQrCountdownUI(remaining);

    qrCountdownTimer = setInterval(() => {
        remaining--;

        if (remaining < 0) {
            clearInterval(qrCountdownTimer);
            return;
        }

        updateStudentQrCountdownUI(remaining);
    }, 1000);
}

function updateStudentQrCountdownUI(seconds) {
    const countdown = document.getElementById("studentQrCountdown");
    const progressBar = document.getElementById("studentQrProgressBar");

    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    const formatted = `${mins}:${secs.toString().padStart(2, "0")}`;

    if (countdown) {
        countdown.innerText = formatted;
    }

    if (progressBar) {
        const percent = Math.max(0, (seconds / QR_WINDOW_SECONDS) * 100);
        progressBar.style.width = `${percent}%`;
    }
}

function startStudentQrAutoRefresh() {
    clearInterval(qrRefreshTimer);

    qrRefreshTimer = setInterval(() => {
        loadStudentRotatingQR();
    }, 5000);
}

function stopStudentQrTimers() {
    clearInterval(qrRefreshTimer);
    clearInterval(qrCountdownTimer);
    qrRefreshTimer = null;
    qrCountdownTimer = null;
}

function showStudentQrError(message) {
    const qrImage = document.getElementById("studentQrImage");
    const countdown = document.getElementById("studentQrCountdown");

    if (qrImage) qrImage.removeAttribute("src");
    if (countdown) countdown.innerText = message;
}

/* ================= OPEN CAMERA ================= */
function openCamera() {
    if (isStudent()) {
        openStudentQR();
        return;
    }

    document.body.classList.add("camera-open");

    const modal = document.getElementById("globalCameraModal");

    if (!modal) {
        alert("Camera modal not found.");
        return;
    }

    mode = "face";

    updateModeUI();

    modal.style.display = "flex";
    modal.style.visibility = "visible";
    modal.style.opacity = "1";

    // delay helps mobile browsers
    setTimeout(() => {
        startCamera();
    }, 300);
}

/* ================= START CAMERA ================= */
async function startCamera() {

    const video = document.getElementById("webcam-feed");

    if (!video) {
        alert("Video element not found.");
        return;
    }

    try {

        // stop old stream first
        if (videoStream) {
            videoStream.getTracks().forEach(track => track.stop());
            videoStream = null;
        }

        const constraints = {
            video: true,
            audio: false
        };

        const stream = await navigator.mediaDevices.getUserMedia(constraints);

        videoStream = stream;

        video.srcObject = stream;

        // IMPORTANT
        video.setAttribute("autoplay", true);
        video.setAttribute("muted", true);
        video.setAttribute("playsinline", true);

        // safer play
        video.onloadedmetadata = () => {
            video.play()
                .then(() => {
                    console.log("Camera started");
                })
                .catch(err => {
                    console.error("Play error:", err);
                });
        };

        resetResult();

    } catch (err) {

        console.error("Camera error:", err);

        alert("Unable to access camera.");
    }

}
/* ================= SWITCH CAMERA ================= */
async function switchCamera() {

    currentFacingMode =
        currentFacingMode === "user"
            ? "environment"
            : "user";

    startCamera();
}

/* ================= MODE ================= */
function setMode(selected, btn) {
    if (isStudent()) return;

    mode = selected;
    updateModeUI(btn);
    resetResult();
}

function updateModeUI(activeBtn = null) {
    const modeText = document.getElementById("modeText");
    const guideText = document.getElementById("scanGuideText");
    const faceBtn = document.getElementById("faceBtn");
    const qrBtn = document.getElementById("qrBtn");

    if (modeText) {
        modeText.innerText = mode === "face" ? "Face Recognition" : "QR Code";
    }

    if (guideText) {
        guideText.innerText = mode === "face"
            ? "Position face within frame"
            : "Position QR code within frame";
    }

    if (faceBtn) {
        faceBtn.classList.remove("btn-primary", "btn-light");
        faceBtn.classList.add(mode === "face" ? "btn-primary" : "btn-light");
    }

    if (qrBtn) {
        qrBtn.classList.remove("btn-primary", "btn-light");
        qrBtn.classList.add(mode === "qr" ? "btn-primary" : "btn-light");
    }
}

/* ================= START DETECTION ================= */
async function startDetection() {

    if (isStudent()) return;
    if (detecting) return;

    resetResult();

    /* =========================================
    QR MODE
    ========================================= */
    if (mode === "qr") {

        const video = document.getElementById("webcam-feed");

        if (!video || video.videoWidth === 0 || video.videoHeight === 0) {

            showFailed("Camera not ready.");

            detecting = false;

            return;
        }

        const canvas = document.createElement("canvas");

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;

        const ctx = canvas.getContext("2d");

        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const imageData = ctx.getImageData(
            0,
            0,
            canvas.width,
            canvas.height
        );

        const qrCode = jsQR(
            imageData.data,
            canvas.width,
            canvas.height
        );

        console.log("QR RESULT:", qrCode);

        if (!qrCode) {

            console.log("NO QR DETECTED");

            showFailed("No QR code detected.");

            detecting = false;

            return;
        }

        try {

            const response = await fetch("/security/verify-qr", {

                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                credentials: "same-origin",

                body: JSON.stringify({
                    qr_token: qrCode.data
                })
            });

            const result = await response.json();

            if (result.success) {

                showSuccess({
                    name: result.student_name || "-",
                    matric: result.matric_no || "-",
                    block: result.block || "-",
                    room: result.room_no || "-",
                    status: "Verified"
                });

            } else {

                showFailed(result.message || "Invalid QR code.");
            }

        } catch (err) {

            console.error("QR VERIFY ERROR:", err);

            showFailed(result.message || "QR verification failed.");
        }

        detecting = false;

        return;
    }

    // =========================================
    // FACE MODE
    // =========================================
    detecting = true;

    const video = document.getElementById("webcam-feed");

    if (!video || video.videoWidth === 0 || video.videoHeight === 0) {

        showFailed("Camera not ready.");

        detecting = false;

        return;
    }

    const canvas = document.createElement("canvas");

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx = canvas.getContext("2d");

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const imageData = canvas.toDataURL("image/jpeg");

    try {

        const response = await fetch("/security/verify-face", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            credentials: "same-origin",

            body: JSON.stringify({
                image: imageData
            })
        });

        const result = await response.json();

        if (result.success) {

            showSuccess({
                name: result.student_name || "-",
                matric: result.matric_no || "-",
                block: result.block || "-",
                room: result.room_no || "-",
                image: result.image_path || "",
                status: result.status || "-"
            });

        } else {

            showFailed(result.message || "Face verification failed.");
        }

    } catch (err) {

        console.error("FACE VERIFY ERROR:", err);

        showFailed("Face verification failed.");
    }

    detecting = false;
}

/* ================= UI STATES ================= */
function showSuccess(data) {
    const placeholder = document.getElementById("resultPlaceholder");
    const failed = document.getElementById("resultFailed");
    const success = document.getElementById("resultSuccess");

    if (placeholder) placeholder.classList.add("d-none");
    if (failed) failed.classList.add("d-none");
    if (success) {
        success.classList.remove("d-none");
        success.style.display = "";
    }

    const resImg = document.getElementById("resImg");
    const resName = document.getElementById("resName");
    const resMatric = document.getElementById("resMatric");
    const resBlock = document.getElementById("resBlock");
    const resRoom = document.getElementById("resRoom");
    const resStatus = document.getElementById("resStatus");

    if (resImg) {
        if (data.image) {
            resImg.src = data.image;
            resImg.style.display = "inline-block";
        } else {
            resImg.removeAttribute("src");
            resImg.style.display = "none";
        }
    }

    if (resName) resName.innerText = data.name || "-";
    if (resMatric) resMatric.innerText = data.matric || "-";
    if (resBlock) resBlock.innerText = data.block || "-";
    if (resRoom) resRoom.innerText = data.room || "-";
    if (resStatus) resStatus.innerText = data.status || "-";
}

function showFailed(msg) {
    const placeholder = document.getElementById("resultPlaceholder");
    const success = document.getElementById("resultSuccess");
    const failed = document.getElementById("resultFailed");
    const failText = document.getElementById("failText");
    const failDesc = document.getElementById("failDesc");

    if (placeholder) placeholder.classList.add("d-none");
    if (success) {
        success.classList.add("d-none");
        success.style.display = "none";
    }
    if (failed) {
        failed.classList.remove("d-none");
        failed.style.display = "";
    }
    if (failText) failText.innerText = msg || "Detection Failed";
    if (failDesc) failDesc.innerText = "Please try again.";
}

function resetResult() {
    const placeholder = document.getElementById("resultPlaceholder");
    const success = document.getElementById("resultSuccess");
    const failed = document.getElementById("resultFailed");
    const failText = document.getElementById("failText");

    const resImg = document.getElementById("resImg");
    const resName = document.getElementById("resName");
    const resMatric = document.getElementById("resMatric");
    const resBlock = document.getElementById("resBlock");
    const resRoom = document.getElementById("resRoom");
    const resStatus = document.getElementById("resStatus");

    if (placeholder) {
        placeholder.classList.remove("d-none");
        placeholder.style.display = "";
    }
    if (success) {
        success.classList.add("d-none");
        success.style.display = "none";
    }
    if (failed) {
        failed.classList.add("d-none");
        failed.style.display = "none";
    }
    if (failText) failText.innerText = "Detection Failed";

    if (resImg) {
        resImg.removeAttribute("src");
        resImg.style.display = "none";
    }
    if (resName) resName.innerText = "";
    if (resMatric) resMatric.innerText = "";
    if (resBlock) resBlock.innerText = "";
    if (resRoom) resRoom.innerText = "";
    if (resStatus) resStatus.innerText = "";
}

function closeCamera() {
    document.body.classList.remove("camera-open");
    stopStudentQrTimers();

    if (videoStream) {
        videoStream.getTracks().forEach(track => track.stop());
        videoStream = null;
    }

    currentFacingMode = "user";

    const video = document.getElementById("webcam-feed");
    if (video) {
        video.pause();
        video.srcObject = null;
    }

    const modal = document.getElementById("globalCameraModal");
    if (modal) {
        modal.style.display = "none";
        modal.style.visibility = "hidden";
        modal.style.opacity = "0";
    }

    resetResult();
    detecting = false;
}

document.addEventListener("DOMContentLoaded", function () {
    mode = isStudent() ? "qr" : "face";
    if (!isStudent()) updateModeUI();
});