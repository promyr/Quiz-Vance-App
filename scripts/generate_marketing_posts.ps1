[CmdletBinding()]
param(
    [string]$LogoPath = "C:\Users\Belchior\IdeaProjects\Quiz Vance App\assets\logo_quizvance.png",
    [string]$OutputDir = "C:\Users\Belchior\IdeaProjects\Quiz Vance App\assets\marketing_posts"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

function New-Color {
    param(
        [int]$A = 255,
        [int]$R,
        [int]$G,
        [int]$B
    )
    return [System.Drawing.Color]::FromArgb($A, $R, $G, $B)
}

function New-RoundedRectPath {
    param(
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$Height,
        [float]$Radius
    )

    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $diameter = $Radius * 2
    $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
    $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
    $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function Draw-WrappedText {
    param(
        [System.Drawing.Graphics]$Graphics,
        [string]$Text,
        [System.Drawing.Font]$Font,
        [System.Drawing.Brush]$Brush,
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$Height,
        [string]$Alignment = "Near"
    )

    $format = New-Object System.Drawing.StringFormat
    $format.Trimming = [System.Drawing.StringTrimming]::EllipsisWord
    $format.FormatFlags = [System.Drawing.StringFormatFlags]::LineLimit
    switch ($Alignment) {
        "Center" { $format.Alignment = [System.Drawing.StringAlignment]::Center }
        "Far" { $format.Alignment = [System.Drawing.StringAlignment]::Far }
        default { $format.Alignment = [System.Drawing.StringAlignment]::Near }
    }
    $Graphics.DrawString($Text, $Font, $Brush, [System.Drawing.RectangleF]::new($X, $Y, $Width, $Height), $format)
    $format.Dispose()
}

function Draw-TextLines {
    param(
        [System.Drawing.Graphics]$Graphics,
        [string[]]$Lines,
        [System.Drawing.Font]$Font,
        [System.Drawing.Brush]$Brush,
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$LineHeight,
        [string]$Alignment = "Near"
    )

    $currentY = $Y
    foreach ($line in $Lines) {
        $lineX = $X
        $lineSize = $Graphics.MeasureString($line, $Font)
        switch ($Alignment) {
            "Center" { $lineX = $X + (($Width - $lineSize.Width) / 2) }
            "Far" { $lineX = $X + ($Width - $lineSize.Width) }
            default { }
        }
        $Graphics.DrawString($line, $Font, $Brush, [float]$lineX, [float]$currentY)
        $currentY += $LineHeight
    }
}

function Draw-GlowCircle {
    param(
        [System.Drawing.Graphics]$Graphics,
        [float]$CenterX,
        [float]$CenterY,
        [float]$Radius,
        [System.Drawing.Color]$Color
    )

    for ($step = 7; $step -ge 1; $step--) {
        $alpha = [Math]::Max(18, [int](16 * $step))
        $size = $Radius * (1 + ($step / 3))
        $brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb($alpha, $Color))
        $Graphics.FillEllipse($brush, $CenterX - ($size / 2), $CenterY - ($size / 2), $size, $size)
        $brush.Dispose()
    }
}

function Draw-Badge {
    param(
        [System.Drawing.Graphics]$Graphics,
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$Height,
        [string]$Text
    )

    $path = New-RoundedRectPath -X $X -Y $Y -Width $Width -Height $Height -Radius 20
    $badgeBrush = New-Object System.Drawing.SolidBrush (New-Color -A 230 -R 16 -G 79 -B 182)
    $badgePen = New-Object System.Drawing.Pen (New-Color -A 255 -R 85 -G 164 -B 255), 2
    $font = New-Object System.Drawing.Font("Segoe UI Semibold", 24, [System.Drawing.FontStyle]::Bold)
    $textBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $Graphics.FillPath($badgeBrush, $path)
    $Graphics.DrawPath($badgePen, $path)
    Draw-WrappedText -Graphics $Graphics -Text $Text -Font $font -Brush $textBrush -X ($X + 20) -Y ($Y + 9) -Width ($Width - 40) -Height ($Height - 18) -Alignment "Center"
    $textBrush.Dispose()
    $font.Dispose()
    $badgePen.Dispose()
    $badgeBrush.Dispose()
    $path.Dispose()
}

function Draw-CanvasBase {
    param(
        [System.Drawing.Graphics]$Graphics,
        [int]$Width,
        [int]$Height
    )

    $Graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
    $Graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $Graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

    $backgroundRect = [System.Drawing.Rectangle]::new(0, 0, $Width, $Height)
    $backgroundBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        $backgroundRect,
        (New-Color -R 10 -G 20 -B 40),
        (New-Color -R 77 -G 82 -B 90),
        20
    )
    $Graphics.FillRectangle($backgroundBrush, $backgroundRect)
    $backgroundBrush.Dispose()

    Draw-GlowCircle -Graphics $Graphics -CenterX ($Width * 0.78) -CenterY ($Height * 0.30) -Radius ($Width * 0.13) -Color (New-Color -R 36 -G 140 -B 255)
    Draw-GlowCircle -Graphics $Graphics -CenterX ($Width * 0.18) -CenterY ($Height * 0.92) -Radius ($Width * 0.05) -Color (New-Color -R 255 -G 255 -B 255)

    $overlayBrush = New-Object System.Drawing.SolidBrush (New-Color -A 40 -R 255 -G 255 -B 255)
    $Graphics.FillEllipse($overlayBrush, -120, -80, 300, 220)
    $Graphics.FillEllipse($overlayBrush, $Width - 220, $Height - 200, 260, 200)
    $overlayBrush.Dispose()
}

function Draw-Logo {
    param(
        [System.Drawing.Graphics]$Graphics,
        [System.Drawing.Image]$LogoImage,
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$Height,
        [float]$Opacity = 1.0
    )

    $cm = New-Object System.Drawing.Imaging.ColorMatrix
    $cm.Matrix33 = [float]$Opacity
    $attributes = New-Object System.Drawing.Imaging.ImageAttributes
    $attributes.SetColorMatrix($cm, [System.Drawing.Imaging.ColorMatrixFlag]::Default, [System.Drawing.Imaging.ColorAdjustType]::Bitmap)
    $destRect = [System.Drawing.Rectangle]::new([int]$X, [int]$Y, [int]$Width, [int]$Height)
    $Graphics.DrawImage($LogoImage, $destRect, 0, 0, $LogoImage.Width, $LogoImage.Height, [System.Drawing.GraphicsUnit]::Pixel, $attributes)
    $attributes.Dispose()
}

function New-Canvas {
    param([int]$Width, [int]$Height)
    $bitmap = New-Object System.Drawing.Bitmap($Width, $Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    Draw-CanvasBase -Graphics $graphics -Width $Width -Height $Height
    return @{ Bitmap = $bitmap; Graphics = $graphics }
}

function Save-Canvas {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [System.Drawing.Graphics]$Graphics,
        [string]$Path
    )
    $Graphics.Dispose()
    $Bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $Bitmap.Dispose()
}

if (-not (Test-Path -LiteralPath $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
}

$logo = [System.Drawing.Image]::FromFile($LogoPath)

try {
    $titleBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
    $bodyBrush = New-Object System.Drawing.SolidBrush (New-Color -R 225 -G 232 -B 238)
    $accentBrush = New-Object System.Drawing.SolidBrush (New-Color -R 124 -G 192 -B 255)

    $titleFont = New-Object System.Drawing.Font("Segoe UI Semibold", 50, [System.Drawing.FontStyle]::Bold)
    $bodyFont = New-Object System.Drawing.Font("Segoe UI", 24, [System.Drawing.FontStyle]::Regular)
    $smallFont = New-Object System.Drawing.Font("Segoe UI Semibold", 22, [System.Drawing.FontStyle]::Bold)
    $storyTitleFont = New-Object System.Drawing.Font("Segoe UI Semibold", 66, [System.Drawing.FontStyle]::Bold)
    $storyBodyFont = New-Object System.Drawing.Font("Segoe UI", 28, [System.Drawing.FontStyle]::Regular)
    $midTitleFont = New-Object System.Drawing.Font("Segoe UI Semibold", 38, [System.Drawing.FontStyle]::Bold)
    $storyMidTitleFont = New-Object System.Drawing.Font("Segoe UI Semibold", 54, [System.Drawing.FontStyle]::Bold)

    $feed = New-Canvas -Width 1080 -Height 1080
    Draw-Logo -Graphics $feed.Graphics -LogoImage $logo -X 110 -Y 120 -Width 860 -Height 460 -Opacity 0.20
    Draw-Badge -Graphics $feed.Graphics -X 90 -Y 88 -Width 330 -Height 62 -Text "BETA ABERTO"
    Draw-WrappedText -Graphics $feed.Graphics -Text "Quiz Vance`npara Android" -Font $titleFont -Brush $titleBrush -X 90 -Y 580 -Width 880 -Height 160
    Draw-WrappedText -Graphics $feed.Graphics -Text "Estude com foco. Avance com pratica." -Font $bodyFont -Brush $accentBrush -X 90 -Y 710 -Width 760 -Height 55
    Draw-WrappedText -Graphics $feed.Graphics -Text "Acesso antecipado ao app, comunidade oficial no Telegram e suporte proximo durante o beta." -Font $bodyFont -Brush $bodyBrush -X 90 -Y 790 -Width 820 -Height 120
    Draw-Badge -Graphics $feed.Graphics -X 90 -Y 952 -Width 390 -Height 58 -Text "DISPONIVEL SO PARA ANDROID"
    Save-Canvas -Bitmap $feed.Bitmap -Graphics $feed.Graphics -Path (Join-Path $OutputDir "quizvance_beta_android_feed.png")

    $android = New-Canvas -Width 1080 -Height 1080
    Draw-Logo -Graphics $android.Graphics -LogoImage $logo -X 230 -Y 110 -Width 620 -Height 380 -Opacity 0.18
    Draw-Badge -Graphics $android.Graphics -X 360 -Y 94 -Width 360 -Height 60 -Text "ANDROID"
    Draw-WrappedText -Graphics $android.Graphics -Text "Primeiros usuarios do beta Android" -Font $midTitleFont -Brush $titleBrush -X 140 -Y 565 -Width 800 -Height 100 -Alignment "Center"
    Draw-WrappedText -Graphics $android.Graphics -Text "Instalacao antecipada antes das lojas, comunidade oficial no Telegram e espaco real para feedback." -Font $bodyFont -Brush $bodyBrush -X 140 -Y 700 -Width 800 -Height 150 -Alignment "Center"
    Draw-WrappedText -Graphics $android.Graphics -Text "Solicite acesso pelos canais oficiais" -Font $smallFont -Brush $accentBrush -X 250 -Y 920 -Width 580 -Height 40 -Alignment "Center"
    Save-Canvas -Bitmap $android.Bitmap -Graphics $android.Graphics -Path (Join-Path $OutputDir "quizvance_primeiros_usuarios_square.png")

    $story = New-Canvas -Width 1080 -Height 1920
    Draw-Logo -Graphics $story.Graphics -LogoImage $logo -X 110 -Y 190 -Width 860 -Height 500 -Opacity 0.18
    Draw-Badge -Graphics $story.Graphics -X 120 -Y 120 -Width 330 -Height 64 -Text "BETA QUIZ VANCE"
    Draw-WrappedText -Graphics $story.Graphics -Text "Agora no Android" -Font $storyMidTitleFont -Brush $titleBrush -X 120 -Y 820 -Width 840 -Height 80
    Draw-WrappedText -Graphics $story.Graphics -Text "Entre cedo, teste o app antes das lojas e acompanhe a evolucao do produto de perto." -Font $storyBodyFont -Brush $bodyBrush -X 120 -Y 980 -Width 820 -Height 190
    $panelPath = New-RoundedRectPath -X 120 -Y 1290 -Width 840 -Height 280 -Radius 38
    $panelBrush = New-Object System.Drawing.SolidBrush (New-Color -A 180 -R 10 -G 25 -B 50)
    $panelPen = New-Object System.Drawing.Pen (New-Color -A 220 -R 79 -G 160 -B 255), 2
    $story.Graphics.FillPath($panelBrush, $panelPath)
    $story.Graphics.DrawPath($panelPen, $panelPath)
    Draw-WrappedText -Graphics $story.Graphics -Text "Disponivel apenas para Android`nComunidade oficial no Telegram`nSolicite acesso pelos canais oficiais" -Font $storyBodyFont -Brush $titleBrush -X 170 -Y 1340 -Width 740 -Height 210 -Alignment "Center"
    $panelPen.Dispose()
    $panelBrush.Dispose()
    $panelPath.Dispose()
    Draw-WrappedText -Graphics $story.Graphics -Text "Estude com foco. Avance com pratica." -Font $smallFont -Brush $accentBrush -X 250 -Y 1655 -Width 580 -Height 40 -Alignment "Center"
    Save-Canvas -Bitmap $story.Bitmap -Graphics $story.Graphics -Path (Join-Path $OutputDir "quizvance_beta_android_story.png")

    $captionPath = Join-Path $OutputDir "copys_marketing_beta.txt"
    @"
POST 1 | FEED
O beta do Quiz Vance para Android esta aberto.

Uma nova fase com acesso antecipado ao app, entrada na comunidade oficial e contato mais proximo com a evolucao do produto.

Disponivel exclusivamente para Android nesta etapa.

POST 2 | FEED
Primeiros usuarios do beta Quiz Vance.

Instalacao antecipada antes das lojas, comunidade oficial no Telegram e espaco real para feedback e melhoria continua.

Disponivel apenas para Android.

POST 3 | STORY
Quiz Vance agora no Android.

Entre cedo no beta, acompanhe a evolucao do app e solicite acesso pelos canais oficiais.
"@ | Set-Content -Path $captionPath -Encoding UTF8

    Write-Output "OK: $(Join-Path $OutputDir 'quizvance_beta_android_feed.png')"
    Write-Output "OK: $(Join-Path $OutputDir 'quizvance_primeiros_usuarios_square.png')"
    Write-Output "OK: $(Join-Path $OutputDir 'quizvance_beta_android_story.png')"
    Write-Output "OK: $captionPath"
}
finally {
    $logo.Dispose()
}
